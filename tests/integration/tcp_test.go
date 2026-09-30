package integration

import (
	"bytes"
	"context"
	"crypto/tls"
	"crypto/x509"
	"errors"
	"net"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/tlsconfig"
	"quic-performance-lab/internal/transport/tcp"
	"quic-performance-lab/internal/workload"
)

func fixture(t *testing.T) (*tls.Config, *tls.Config, *workload.Store) {
	t.Helper()
	dir := t.TempDir()
	if b, err := exec.Command("bash", "../../scripts/gen-cert.sh", "--dir", dir).CombinedOutput(); err != nil {
		t.Fatalf("cert: %v %s", err, b)
	}
	srv, err := tlsconfig.Server(filepath.Join(dir, "server.crt"), filepath.Join(dir, "server.key"))
	if err != nil {
		t.Fatal(err)
	}
	client, err := tlsconfig.Client(filepath.Join(dir, "server.crt"), "localhost")
	if err != nil {
		t.Fatal(err)
	}
	w, err := config.LoadWorkloads("../../configs/workloads.json")
	if err != nil {
		t.Fatal(err)
	}
	store, err := workload.NewStore(w.Profiles["handshake"], w.Limits)
	if err != nil {
		t.Fatal(err)
	}
	return srv, client, store
}

func TestTCPRealLocalhostAndTrust(t *testing.T) {
	srv, client, store := fixture(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	ready := make(chan net.Addr)
	done := make(chan error, 1)
	go func() {
		done <- tcp.Serve(ctx, "127.0.0.1:0", srv, store, tcp.ServerOptions{HandshakeTimeout: time.Second, TrialTimeout: time.Second, MaxConnections: 8}, ready)
	}()
	var addr net.Addr
	select {
	case addr = <-ready:
	case err := <-done:
		t.Fatalf("server setup: %v", err)
	case <-time.After(2 * time.Second):
		t.Fatal("server readiness timeout")
	}
	result, err := tcp.Run(context.Background(), addr.String(), client, store, 2*time.Second)
	if err != nil {
		t.Fatal(err)
	}
	if !result.ChecksumOK || result.BytesExpected != 1024 || result.BytesReceived != 1024 {
		t.Fatalf("bad transfer %+v", result)
	}
	timing := result.Timing
	if timing.Start.IsZero() || timing.TCPConnected.Before(timing.Start) || timing.Handshake.Before(timing.TCPConnected) || timing.RequestStart.Before(timing.Handshake) || timing.FirstByte.Before(timing.RequestStart) || timing.Done.Before(timing.FirstByte) {
		t.Fatalf("invalid actual timing %+v", timing)
	}
	t.Logf("real localhost TCP/TLS: bytes=%d checksum_ok=%t elapsed=%s", result.BytesReceived, result.ChecksumOK, timing.Done.Sub(timing.Start))
	bad := client.Clone()
	bad.RootCAs = x509.NewCertPool()
	if _, err := tcp.Run(context.Background(), addr.String(), bad, store, time.Second); err == nil {
		t.Fatal("untrusted server certificate accepted")
	} else {
		t.Logf("untrusted cert rejected: %v", err)
	}
	cancel()
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("server did not stop")
	}
}

func TestTCPMalformedPeersBounded(t *testing.T) {
	srv, client, store := fixture(t)
	for name, reply := range map[string]func(*tls.Conn){
		"truncated frame": func(c *tls.Conn) { c.Write([]byte("QB01")) },
		"bad length": func(c *tls.Conn) {
			var b bytes.Buffer
			_ = protocol.WriteFrame(&b, protocol.MetaFrame(1, 1024, [32]byte{}), 1024)
			p := b.Bytes()
			p[20], p[21], p[22], p[23] = 0xff, 0xff, 0xff, 0xff
			c.Write(p[:24])
		},
		"timeout": func(c *tls.Conn) { var p [1]byte; c.Read(p[:]) },
	} {
		t.Run(name, func(t *testing.T) {
			ln, err := net.Listen("tcp", "127.0.0.1:0")
			if err != nil {
				t.Fatal(err)
			}
			defer ln.Close()
			done := make(chan struct{})
			go func() {
				defer close(done)
				raw, err := ln.Accept()
				if err != nil {
					return
				}
				c := tls.Server(raw, srv)
				defer c.Close()
				_ = c.SetDeadline(time.Now().Add(time.Second))
				if c.Handshake() != nil {
					return
				}
				_, _ = protocol.ReadFrame(c, 1024)
				reply(c)
			}()
			started := time.Now()
			_, err = tcp.Run(context.Background(), ln.Addr().String(), client, store, 150*time.Millisecond)
			if err == nil {
				t.Fatal("malformed peer accepted")
			}
			if time.Since(started) > time.Second {
				t.Fatalf("peer hung: %v", err)
			}
			select {
			case <-done:
			case <-time.After(2 * time.Second):
				t.Fatal("peer handler leaked")
			}
			t.Logf("%s rejected in %s: %v", name, time.Since(started), err)
		})
	}
}

func TestTCPCancelReleasesHandler(t *testing.T) {
	srv, _, store := fixture(t)
	ctx, cancel := context.WithCancel(context.Background())
	ready := make(chan net.Addr)
	done := make(chan error, 1)
	go func() {
		done <- tcp.Serve(ctx, "127.0.0.1:0", srv, store, tcp.ServerOptions{HandshakeTimeout: time.Second, TrialTimeout: 10 * time.Second, MaxConnections: 8}, ready)
	}()
	var addr net.Addr
	select {
	case addr = <-ready:
	case err := <-done:
		t.Fatalf("server setup: %v", err)
	case <-time.After(2 * time.Second):
		t.Fatal("server readiness timeout")
	}
	raw, err := net.Dial("tcp", addr.String())
	if err != nil {
		t.Fatal(err)
	}
	defer raw.Close()
	// Handler may be in TLS handshake or request read; cancellation closes it.
	cancel()
	select {
	case err := <-done:
		if err != nil && !errors.Is(err, context.Canceled) {
			t.Fatal(err)
		}
	case <-time.After(time.Second):
		t.Fatal("cancel did not release handler")
	}
}
