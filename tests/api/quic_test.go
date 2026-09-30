// Compile-only API contracts for the pinned module. This is not a QUIC transfer test.
package api_test

import (
	"context"
	"crypto/tls"
	"io"
	"net"
	"testing"
	"time"

	quic "github.com/quic-go/quic-go"
	"github.com/quic-go/quic-go/qlog"
	"github.com/quic-go/quic-go/qlogwriter"
)

var (
	_ func(context.Context, net.PacketConn, net.Addr, *tls.Config, *quic.Config) (*quic.Conn, error)  = quic.Dial
	_ func(context.Context, net.PacketConn, net.Addr, *tls.Config, *quic.Config) (*quic.Conn, error)  = quic.DialEarly
	_ func(net.PacketConn, *tls.Config, *quic.Config) (*quic.Listener, error)                         = quic.Listen
	_ func(net.PacketConn, *tls.Config, *quic.Config) (*quic.EarlyListener, error)                    = quic.ListenEarly
	_ func(*quic.Transport, context.Context, net.Addr, *tls.Config, *quic.Config) (*quic.Conn, error) = (*quic.Transport).DialEarly
	_ func(*quic.Listener, context.Context) (*quic.Conn, error)                                       = (*quic.Listener).Accept
	_ func(*quic.EarlyListener, context.Context) (*quic.Conn, error)                                  = (*quic.EarlyListener).Accept
	_ func(*quic.Conn) (*quic.Stream, error)                                                          = (*quic.Conn).OpenStream
	_ func(*quic.Conn, context.Context) (*quic.Stream, error)                                         = (*quic.Conn).OpenStreamSync
	_ func(*quic.Conn, context.Context) (*quic.Stream, error)                                         = (*quic.Conn).AcceptStream
	_ func(*quic.Conn) <-chan struct{}                                                                = (*quic.Conn).HandshakeComplete
	_ func(*quic.Conn, context.Context) (*quic.Conn, error)                                           = (*quic.Conn).NextConnection
	_ func(*quic.Conn) quic.ConnectionState                                                           = (*quic.Conn).ConnectionState
	_ func(*quic.Conn, quic.ApplicationErrorCode, string) error                                       = (*quic.Conn).CloseWithError
	_ func(*quic.Stream) quic.StreamID                                                                = (*quic.Stream).StreamID
	_ func(*quic.Stream) error                                                                        = (*quic.Stream).Close
	_ func(*quic.Stream, quic.StreamErrorCode)                                                        = (*quic.Stream).CancelRead
	_ func(*quic.Stream, quic.StreamErrorCode)                                                        = (*quic.Stream).CancelWrite
	_ func(*quic.Stream, time.Time) error                                                             = (*quic.Stream).SetDeadline
	_ func(*quic.Stream, time.Time) error                                                             = (*quic.Stream).SetReadDeadline
	_ func(*quic.Stream, time.Time) error                                                             = (*quic.Stream).SetWriteDeadline
	_ func(context.Context, bool, quic.ConnectionID) qlogwriter.Trace                                 = qlog.DefaultConnectionTracer
	_ func(io.WriteCloser, bool, qlogwriter.ConnectionID, []string) *qlogwriter.FileSeq               = qlogwriter.NewConnectionFileSeq
)

func TestPinnedAPI(t *testing.T) {
	_ = quic.Config{Versions: []quic.Version{quic.Version1}, Allow0RTT: true,
		MaxIncomingStreams: 64, MaxIncomingUniStreams: -1,
		HandshakeIdleTimeout: 5 * time.Second, MaxIdleTimeout: 60 * time.Second,
		InitialStreamReceiveWindow: 512 << 10, MaxStreamReceiveWindow: 6 << 20,
		InitialConnectionReceiveWindow: 512 << 10, MaxConnectionReceiveWindow: 15 << 20,
		Tracer: qlog.DefaultConnectionTracer}
	var state quic.ConnectionState
	var used, resumed bool = state.Used0RTT, state.TLS.DidResume
	_, _ = used, resumed // Type checks only: never emitted as measured state.
	var _ error = quic.Err0RTTRejected
	var _ tls.ClientSessionCache = tls.NewLRUClientSessionCache(1)
	t.Log("Pinned Dial/Listen/stream/early/qlog signatures compile; no network called")
}
