package quic

import (
	"time"

	quicgo "github.com/quic-go/quic-go"
)

// These are advertised receive credits, not application buffers. The reader
// consumes frames as they arrive; quic-go can grow windows up to these caps.
const (
	initialStreamWindow = 512 << 10
	maxStreamWindow     = 2 << 20
	initialConnWindow   = 2 << 20
	maxConnWindow       = 16 << 20
	maxBidiStreams      = 64
)

func quicConfig(handshakeTimeout, trialTimeout time.Duration) *quicgo.Config {
	return &quicgo.Config{
		Versions: []quicgo.Version{quicgo.Version1},
		// quic-go allows a handshake for up to 2x this idle timeout.
		HandshakeIdleTimeout:           max(handshakeTimeout/2, time.Nanosecond),
		MaxIdleTimeout:                 trialTimeout,
		MaxIncomingStreams:             maxBidiStreams,
		MaxIncomingUniStreams:          -1,
		InitialStreamReceiveWindow:     initialStreamWindow,
		MaxStreamReceiveWindow:         maxStreamWindow,
		InitialConnectionReceiveWindow: initialConnWindow,
		MaxConnectionReceiveWindow:     maxConnWindow,
	}
}
