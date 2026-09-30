// Package cli dispatches phase-supported commands; later-phase modes stay nonzero.
package cli

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"runtime/debug"
	"strconv"
	"syscall"
	"time"

	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/tlsconfig"
	"quic-performance-lab/internal/transport"
	quictransport "quic-performance-lab/internal/transport/quic"
	tcptransport "quic-performance-lab/internal/transport/tcp"
	"quic-performance-lab/internal/workload"

	quic "github.com/quic-go/quic-go"
)

// Set by the Makefile; direct go build still reports its actual toolchain/modules.
var Build = "development"

func Version(name string) string {
	commit, dirty, qv := "uncommitted", "unknown", "unknown"
	if b, ok := debug.ReadBuildInfo(); ok {
		for _, s := range b.Settings {
			switch s.Key {
			case "vcs.revision":
				commit = s.Value
			case "vcs.modified":
				dirty = s.Value
			}
		}
		for _, d := range b.Deps {
			if d.Path == "github.com/quic-go/quic-go" {
				qv = d.Version
				if d.Replace != nil {
					qv += " (replaced)"
				}
			}
		}
	}
	return fmt.Sprintf("%s build=%s commit=%s dirty=%s Go=%s quic-go=%s QUIC=%s", name, Build, commit, dirty, runtime.Version(), qv, quic.Version1)
}

func endpoint(s string) bool {
	h, p, err := net.SplitHostPort(s)
	if err != nil || h == "" {
		return false
	}
	n, err := strconv.Atoi(p)
	return err == nil && n > 0 && n <= 65535
}

func Run(name string, args []string, out, errOut io.Writer) int {
	fs := flag.NewFlagSet(name, flag.ContinueOnError)
	fs.SetOutput(errOut)
	fs.Usage = func() {
		fmt.Fprintf(errOut, "Usage: %s [flags]\nP4: TCP/TLS and QUIC cold batch transfer; benchmark and 0-RTT modes report not implemented.\n", name)
		fs.PrintDefaults()
	}
	version := fs.Bool("version", false, "print build, commit and toolchain versions")
	profiles := fs.String("profiles", config.DefaultProfiles, "workload JSON file")
	profile := fs.String("profile", "bulk", "workload profile")
	var transportName, addr, mode, format, ca, serverName, cert, key, readyFile, scenario, suite, entry, merge string
	var timeout time.Duration
	var runs, warmups int
	var plan bool
	fs.String("qlog-dir", "", "qlog directory (future evidence mode)")
	fs.String("keylog", "", "TLS secrets file (future evidence mode)")
	if name == "server" {
		fs.StringVar(&addr, "listen", "0.0.0.0:4433", "listen endpoint")
		fs.StringVar(&transportName, "transport", "both", "tcp, quic or both")
		fs.StringVar(&cert, "cert", "certs/server.crt", "certificate PEM")
		fs.StringVar(&key, "key", "certs/server.key", "private key PEM")
		fs.Bool("allow-0rtt", true, "allow read-only QUIC early data (future phase)")
		fs.StringVar(&readyFile, "ready-file", "", "atomic readiness path")
	} else if name == "client" || name == "bench" {
		fs.StringVar(&addr, "addr", "10.10.0.2:4433", "server endpoint")
		fs.StringVar(&transportName, "transport", "tcp", "tcp or quic")
		fs.StringVar(&mode, "mode", "cold", "cold, resumed or early; non-cold requires quic")
		fs.StringVar(&ca, "ca", "certs/server.crt", "explicit trusted certificate/CA")
		fs.StringVar(&serverName, "server-name", "10.10.0.2", "TLS peer identity")
		fs.DurationVar(&timeout, "timeout", 0, "trial deadline (default: timeouts.trial_seconds from profiles)")
		fs.StringVar(&format, "format", "table", "table or json")
		fs.String("experiment-id", "", "experiment identifier")
		fs.String("run-id", "", "trial identifier")
		fs.String("out", "", "result directory (canonical files arrive in P6)")
		fs.Bool("progress", false, "collect progress in future evidence mode")
	} else {
		fmt.Fprintln(errOut, "unknown binary")
		return 2
	}
	scenarios := config.DefaultScenarios
	if name == "bench" {
		fs.StringVar(&scenarios, "scenarios", config.DefaultScenarios, "scenario JSON file")
		fs.StringVar(&scenario, "scenario", "rtt50-loss3", "scenario name")
		fs.IntVar(&runs, "runs", 0, "measured repeats (default: scenario config)")
		fs.IntVar(&warmups, "warmups", 0, "warmups (default: scenario config)")
		fs.BoolVar(&plan, "plan", false, "schedule planning (future phase)")
		fs.StringVar(&suite, "suite", "bulk", "bulk or handshake")
		fs.Uint64("seed", 0, "schedule seed (default: scenario config; planning in future phase)")
		fs.StringVar(&entry, "schedule-entry", "", "entry JSON path (future phase)")
		fs.StringVar(&merge, "merge", "", "shard directory (future phase)")
		fs.String("network-state", "", "verified network metadata path")
	}
	if err := fs.Parse(args); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}
	bad := func(s string) int { fmt.Fprintln(errOut, "invalid input:", s); return 2 }
	if fs.NArg() != 0 {
		return bad("unexpected positional arguments")
	}
	if *version {
		fmt.Fprintln(out, Version(name))
		return 0
	}
	w, err := config.LoadWorkloads(*profiles)
	if err != nil {
		return bad(err.Error())
	}
	if _, ok := w.Profiles[*profile]; !ok {
		return bad("unknown workload profile")
	}
	if !endpoint(addr) {
		return bad("endpoint must have host and port 1..65535")
	}
	if transportName != "tcp" && transportName != "quic" && !(name == "server" && transportName == "both") {
		return bad("unsupported transport")
	}
	if name == "server" {
		if cert == "" || key == "" {
			return bad("cert/key cannot be empty")
		}
	} else {
		if mode != "cold" && mode != "resumed" && mode != "early" {
			return bad("unsupported mode")
		}
		if transportName != "quic" && mode != "cold" {
			return bad("resumed/early require QUIC")
		}
		explicitTimeout := false
		fs.Visit(func(f *flag.Flag) {
			if f.Name == "timeout" {
				explicitTimeout = true
			}
		})
		if !explicitTimeout {
			timeout = time.Duration(w.Timeouts.TrialSeconds) * time.Second
		}
		if timeout <= 0 || timeout > time.Hour {
			return bad("timeout must be positive and at most 1h")
		}
		if ca == "" || serverName == "" {
			return bad("ca/server-name cannot be empty")
		}
		if format != "table" && format != "json" {
			return bad("format must be table or json")
		}
	}
	if name == "bench" {
		s, err := config.LoadScenarios(scenarios)
		if err != nil {
			return bad(err.Error())
		}
		seen := map[string]bool{}
		fs.Visit(func(f *flag.Flag) { seen[f.Name] = true })
		if !seen["runs"] {
			runs = s.MainRunsPerTransport
		}
		if !seen["warmups"] {
			warmups = s.WarmupsPerTransport
		}
		if runs < 1 || runs > 100000 || warmups < 0 || warmups > 100000 {
			return bad("invalid repeat counts")
		}
		found := false
		for _, v := range s.Scenarios {
			if v.Name == scenario {
				found = true
			}
		}
		if !found {
			return bad("unknown scenario")
		}
		if suite != "bulk" && suite != "handshake" {
			return bad("unknown suite")
		}
		n := 0
		if plan {
			n++
		}
		if entry != "" {
			n++
		}
		if merge != "" {
			n++
		}
		if n > 1 {
			return bad("plan, schedule-entry and merge are mutually exclusive")
		}
	}
	if name == "server" {
		store, err := workload.NewStore(w.Profiles[*profile], w.Limits)
		if err != nil {
			return bad(err.Error())
		}
		cfg, err := tlsconfig.Server(cert, key)
		if err != nil {
			fmt.Fprintln(errOut, err)
			return 1
		}
		ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
		defer stop()
		if err := serveCLI(ctx, addr, transportName, cfg, store, tcptransport.ServerOptions{
			HandshakeTimeout: time.Duration(w.Timeouts.HandshakeSeconds) * time.Second,
			BatchTimeout:     time.Duration(w.Timeouts.BatchSeconds) * time.Second,
			TrialTimeout:     time.Duration(w.Timeouts.TrialSeconds) * time.Second,
			MaxConnections:   int(w.Limits.MaxActiveConnections),
		}, readyFile, *profile, errOut); err != nil {
			fmt.Fprintln(errOut, err)
			return 1
		}
		return 0
	}
	if name == "client" && mode == "cold" {
		expected, err := workload.NewStore(w.Profiles[*profile], w.Limits)
		if err != nil {
			return bad(err.Error())
		}
		cfg, err := tlsconfig.Client(ca, serverName)
		if err != nil {
			fmt.Fprintln(errOut, err)
			return 1
		}
		var results []transport.Result
		if transportName == "tcp" {
			results, err = tcptransport.RunBatch(context.Background(), addr, cfg, expected, timeout)
		} else {
			results, err = quictransport.RunBatch(context.Background(), addr, cfg, expected, timeout)
		}
		if err != nil {
			fmt.Fprintln(errOut, transportName, "transfer failed:", err)
			return 1
		}
		if err := writeTransfer(out, transportName, *profile, format, results); err != nil {
			fmt.Fprintln(errOut, err)
			return 1
		}
		return 0
	}
	fmt.Fprintln(errOut, "not implemented: selected transport/mode or benchmark belongs to a later phase")
	return 1
}

func writeTransfer(out io.Writer, transportName, profile, format string, results []transport.Result) error {
	elapsed := float64(results[0].Timing.End.Sub(results[0].Timing.Start)) / float64(time.Millisecond)
	if format == "json" {
		if len(results) == 1 {
			r := results[0]
			return json.NewEncoder(out).Encode(struct {
				Transport         string  `json:"transport"`
				Profile           string  `json:"profile"`
				ResourceID        uint32  `json:"resource_id"`
				TransportStreamID *int64  `json:"transport_stream_id,omitempty"`
				Bytes             uint64  `json:"bytes"`
				ChecksumOK        bool    `json:"checksum_ok"`
				ElapsedMS         float64 `json:"elapsed_ms"`
			}{transportName, profile, r.ResourceID, r.StreamID, r.BytesReceived, r.ChecksumOK, elapsed})
		}
		type row struct {
			ResourceID        uint32 `json:"resource_id"`
			TransportStreamID *int64 `json:"transport_stream_id,omitempty"`
			Bytes             uint64 `json:"bytes"`
			ChecksumOK        bool   `json:"checksum_ok"`
		}
		rows := make([]row, len(results))
		var total uint64
		for i, r := range results {
			rows[i] = row{r.ResourceID, r.StreamID, r.BytesReceived, r.ChecksumOK}
			total += r.BytesReceived
		}
		return json.NewEncoder(out).Encode(struct {
			Transport     string  `json:"transport"`
			Profile       string  `json:"profile"`
			ResourceCount int     `json:"resource_count"`
			Bytes         uint64  `json:"bytes"`
			ElapsedMS     float64 `json:"elapsed_ms"`
			Resources     []row   `json:"resources"`
		}{transportName, profile, len(results), total, elapsed, rows})
	}
	for _, r := range results {
		if r.StreamID != nil {
			if _, err := fmt.Fprintf(out, "%s %s resource=%d stream=%d bytes=%d checksum_ok=%t elapsed_ms=%.3f\n", transportName, profile, r.ResourceID, *r.StreamID, r.BytesReceived, r.ChecksumOK, elapsed); err != nil {
				return err
			}
		} else if _, err := fmt.Fprintf(out, "%s %s resource=%d bytes=%d checksum_ok=%t elapsed_ms=%.3f\n", transportName, profile, r.ResourceID, r.BytesReceived, r.ChecksumOK, elapsed); err != nil {
			return err
		}
	}
	return nil
}

func serveCLI(parent context.Context, addr, transportName string, cfg *tls.Config, store *workload.Store, tcpOpts tcptransport.ServerOptions, readyFile, profile string, errOut io.Writer) error {
	var tcpListener net.Listener
	var packet net.PacketConn
	var quicListener *quic.Listener
	var err error
	if transportName == "tcp" || transportName == "both" {
		tcpListener, err = net.Listen("tcp", addr)
		if err != nil {
			return err
		}
		defer tcpListener.Close()
	}
	quicOpts := quictransport.ServerOptions{
		HandshakeTimeout: tcpOpts.HandshakeTimeout,
		BatchTimeout:     tcpOpts.BatchTimeout,
		TrialTimeout:     tcpOpts.TrialTimeout,
		MaxConnections:   tcpOpts.MaxConnections,
	}
	if transportName == "quic" || transportName == "both" {
		udpAddr := addr
		if tcpListener != nil {
			host, _, _ := net.SplitHostPort(addr)
			_, port, _ := net.SplitHostPort(tcpListener.Addr().String())
			udpAddr = net.JoinHostPort(host, port)
		}
		packet, err = net.ListenPacket("udp", udpAddr)
		if err != nil {
			return err
		}
		defer packet.Close()
		quicListener, err = quictransport.ListenPacket(packet, cfg, quicOpts)
		if err != nil {
			return err
		}
		defer quicListener.Close()
	}
	// One semaphore bounds all active trials across both listeners.
	slots := make(chan struct{}, tcpOpts.MaxConnections)
	tcpOpts.ConnectionSlots, quicOpts.ConnectionSlots = slots, slots
	serverCtx, cancel := context.WithCancel(parent)
	defer cancel()
	done := make(chan error, 2)
	running := 0
	if tcpListener != nil {
		running++
		go func() { done <- tcptransport.ServeListener(serverCtx, tcpListener, cfg, store, tcpOpts) }()
	}
	if quicListener != nil {
		running++
		go func() { done <- quictransport.ServeListener(serverCtx, quicListener, store, quicOpts) }()
	}
	tcpAddress, udpAddress := "none", "none"
	if tcpListener != nil {
		tcpAddress = tcpListener.Addr().String()
	}
	if quicListener != nil {
		udpAddress = quicListener.Addr().String()
	}
	readyText := fmt.Sprintf("%s ready tcp=%s udp=%s profile=%s resources=%d\n", transportName, tcpAddress, udpAddress, profile, store.Count())
	if readyFile != "" {
		if err := writeReadyFile(readyFile, readyText); err != nil {
			cancel()
			for range running {
				<-done
			}
			return err
		}
		defer os.Remove(readyFile)
	}
	if _, err := io.WriteString(errOut, readyText); err != nil {
		cancel()
		for range running {
			<-done
		}
		return err
	}
	var firstErr error
	for range running {
		if err := <-done; err != nil && firstErr == nil {
			firstErr = err
			cancel()
		}
	}
	return firstErr
}

func writeReadyFile(path, data string) error {
	tmp, err := os.CreateTemp(filepath.Dir(path), ".quiclab-ready-*")
	if err != nil {
		return err
	}
	defer os.Remove(tmp.Name())
	if _, err := io.WriteString(tmp, data); err != nil {
		tmp.Close()
		return err
	}
	if err := tmp.Close(); err != nil {
		return err
	}
	// A hard link publishes the complete file atomically and fails if another
	// process already owns the readiness path.
	return os.Link(tmp.Name(), path)
}
