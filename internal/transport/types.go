// Package transport holds the trial result shared by CLI and future bench code.
package transport

import "time"

type Timing struct {
	Start, TCPConnected, EarlyReady, Handshake, RequestStart, RequestEnd time.Time
	FirstByte, PayloadDone, Done, End                                    time.Time
}

type Result struct {
	Connection   *ConnectionInfo
	Session      *SessionState
	AttemptIndex int
	ResourceID   uint32
	// StreamID is the native QUIC stream ID. It is nil for TCP.
	StreamID        *int64
	BytesExpected   uint64
	BytesReceived   uint64
	ChecksumChecked bool
	Err             error
	ChecksumOK      bool
	Timing          Timing
}

type SessionState struct {
	Attempted0RTT bool
	EarlyRejected *bool
	FallbackCount int
}

// Attempts retain old stream milestones without mixing them into final rows.
type Attempt struct {
	Index   int
	Results []Result
	Err     error
}

type Outcome struct {
	Results        []Result
	Warmup         []Result
	WarmupErr      error
	TicketObserved bool
	Attempts       []Attempt
	Err            error
}
