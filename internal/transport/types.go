// Package transport holds the trial result shared by CLI and future bench code.
package transport

import "time"

type Timing struct {
	Start, TCPConnected, EarlyReady, Handshake, RequestStart, RequestEnd time.Time
	FirstByte, PayloadDone, Done, End                                    time.Time
}

type Result struct {
	Connection *ConnectionInfo
	ResourceID uint32
	// StreamID is the native QUIC stream ID. It is nil for TCP.
	StreamID        *int64
	BytesExpected   uint64
	BytesReceived   uint64
	ChecksumChecked bool
	Err             error
	ChecksumOK      bool
	Timing          Timing
}
