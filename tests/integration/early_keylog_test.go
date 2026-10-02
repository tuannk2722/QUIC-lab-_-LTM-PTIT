package integration

import (
	"bytes"
	"context"
	"io"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"quic-performance-lab/internal/observability"
	quictransport "quic-performance-lab/internal/transport/quic"
)

type failEarlyKeylog struct{ io.Writer }

func (w failEarlyKeylog) Write(p []byte) (int, error) {
	if bytes.HasPrefix(p, []byte("CLIENT_EARLY_TRAFFIC_SECRET ")) {
		return 0, io.ErrClosedPipe
	}
	return w.Writer.Write(p)
}

// Read secrets only inside the test; never include secret values in logs.
func earlySecrets(t *testing.T, path string) map[string]string {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(path)
	if err != nil || info.Mode().Perm() != 0600 {
		t.Fatal("keylog permissions differ", err)
	}
	keys := make(map[string]string)
	for _, line := range strings.Split(string(b), "\n") {
		parts := strings.Fields(line)
		if len(parts) == 3 && parts[0] == "CLIENT_EARLY_TRAFFIC_SECRET" {
			if len(parts[1]) != 64 || (len(parts[2]) != 64 && len(parts[2]) != 96) {
				t.Fatal("invalid early keylog field lengths")
			}
			keys[parts[1]] = parts[2]
		}
	}
	return keys
}

func TestEvidenceEarlyKeylog(t *testing.T) {
	for _, name := range []string{"cold", "resumed", "early", "rejected", "client_writer_error", "server_writer_error"} {
		t.Run(name, func(t *testing.T) {
			srv, client, _ := fixture(t)
			root := t.TempDir()
			serverPath, clientPath := filepath.Join(root, "server.keylog"), filepath.Join(root, "client.keylog")
			sm, err := observability.New("", serverPath)
			if err != nil {
				t.Fatal(err)
			}
			defer sm.Close()
			cm, err := observability.New("", clientPath)
			if err != nil {
				t.Fatal(err)
			}
			defer cm.Close()
			sm.TLS(srv)
			cm.TLS(client)
			if name == "client_writer_error" {
				client.KeyLogWriter = failEarlyKeylog{client.KeyLogWriter}
			}
			if name == "server_writer_error" {
				srv.KeyLogWriter = failEarlyKeylog{srv.KeyLogWriter}
			}
			var accept atomic.Bool
			accept.Store(true)
			opts := earlyOptions()
			opts.Accept0RTT = accept.Load
			store := quicStore(t, 1, 1024, 1024)
			addr, stop := startQUICForTest(t, "127.0.0.1:0", srv, store, opts)
			defer stop()
			mode := name
			if mode != "cold" && mode != "resumed" {
				mode = "early"
			}
			session := quictransport.SessionOptions{Mode: mode, Timeout: 3 * time.Second, TicketTimeout: time.Second}
			if name == "rejected" {
				session.AfterWarmup = func() error { accept.Store(false); return nil }
			}
			out := quictransport.RunSession(context.Background(), addr, client, store, session)
			stop()
			if err := cm.Close(); err != nil {
				t.Fatal(err)
			}
			if err := sm.Close(); err != nil {
				t.Fatal(err)
			}
			if strings.HasSuffix(name, "writer_error") {
				if out.Err == nil {
					t.Fatal("early KeyLogWriter error did not fail the handshake")
				}
				t.Log("early keylog write failure propagated")
				return
			}
			if out.Err != nil || len(out.Results) != 1 || !out.Results[0].ChecksumOK || out.Results[0].BytesReceived != 1024 {
				t.Fatal("transfer failed", out.Err)
			}
			ck, sk := earlySecrets(t, clientPath), earlySecrets(t, serverPath)
			if name == "early" {
				if len(ck) != 1 || len(sk) != 1 || out.Results[0].Connection.Used0RTT == nil || !*out.Results[0].Connection.Used0RTT {
					t.Fatal("accepted early secret/state missing; use make test with pinned TLS overlay")
				}
				for random, secret := range ck {
					if sk[random] != secret {
						t.Fatal("client/server early secrets disagree")
					}
				}
			} else if name == "rejected" {
				if len(ck) != 1 || len(sk) != 0 || out.Results[0].Session.FallbackCount != 1 {
					t.Fatal("rejection secret/replay semantics differ")
				}
			} else if len(ck) != 0 || len(sk) != 0 {
				t.Fatal("cold/resumed generated unexpected early secret")
			}
			t.Logf("mode=%s client_early_labels=%d server_early_labels=%d bytes=1024", name, len(ck), len(sk))
		})
	}
}
