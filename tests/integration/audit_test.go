package integration

import (
	"context"
	"crypto/tls"
	"net"
	"testing"
	"time"

	"quic-performance-lab/internal/metrics"
	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/transport/tcp"
)

func TestTCPAuditChecksumAndEOFFailure(t *testing.T) {
	for _, mode := range []string{"checksum", "eof_timeout"} {
		t.Run(mode, func(t *testing.T) {
			srv, client, _ := fixture(t)
			store := quicStore(t, 3, 1024, 1024)
			ln, err := net.Listen("tcp", "127.0.0.1:0")
			if err != nil {
				t.Fatal(err)
			}
			defer ln.Close()
			release, done := make(chan struct{}), make(chan struct{})
			defer func() { close(release); <-done }()
			go func() {
				defer close(done)
				raw, err := ln.Accept()
				if err != nil {
					return
				}
				conn := tls.Server(raw, srv)
				defer conn.Close()
				conn.SetDeadline(time.Now().Add(3 * time.Second))
				for range 3 {
					if _, err := protocol.ReadFrame(conn, 1024); err != nil {
						return
					}
				}
				for id := uint32(1); id <= 3; id++ {
					r, _ := store.Resource(id)
					data := make([]byte, 1024)
					r.ReadAt(data, 0)
					if mode == "checksum" && id == 2 {
						data[0] ^= 1
					}
					for _, f := range []protocol.Frame{protocol.MetaFrame(id, 1024, r.SHA256()), {Type: protocol.Data, ResourceID: id, Payload: data}, {Type: protocol.Fin, ResourceID: id, Offset: 1024}} {
						if protocol.WriteFrame(conn, f, 1024) != nil {
							return
						}
					}
				}
				if mode == "eof_timeout" {
					select {
					case <-release:
					case <-time.After(2 * time.Second):
					}
				}
			}()
			rows, failure := tcp.RunBatch(context.Background(), ln.Addr().String(), client, store, 500*time.Millisecond)
			if failure == nil {
				t.Fatal("invalid trial succeeded")
			}
			record, err := metrics.NewTrial(metrics.TrialMeta{Transport: "tcp", ResourceCount: 3, ResourceSizeBytes: 1024}, rows, failure)
			if err != nil {
				t.Fatal(err)
			}
			if mode == "checksum" {
				if record.Streams[1].ChecksumOK == nil || *record.Streams[1].ChecksumOK || !record.Streams[0].Success || !record.Streams[2].Success {
					t.Fatalf("%+v", record)
				}
			} else if record.Run.ErrorCode != "timeout" {
				t.Fatalf("error code %s: %v", record.Run.ErrorCode, failure)
			}
		})
	}
}
