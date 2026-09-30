// Package transport holds the trial result shared by CLI and future bench code.
package transport

import "time"

type Timing struct {
	Start, TCPConnected, Handshake, RequestStart, RequestEnd time.Time
	FirstByte, PayloadDone, Done, End                        time.Time
}

type Result struct {
	ResourceID    uint32
	BytesExpected uint64
	BytesReceived uint64
	ChecksumOK    bool
	Timing        Timing
}
