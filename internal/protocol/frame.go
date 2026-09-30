// Package protocol implements the QB01 application framing used by TCP and QUIC.
package protocol

import (
	"bytes"
	"encoding/binary"
	"fmt"
)

const HeaderSize = 24
const (
	Request uint8 = 1
	Data    uint8 = 2
	Fin     uint8 = 3
	Error   uint8 = 4
	Meta    uint8 = 5
)

type Frame struct {
	Type       uint8
	ResourceID uint32
	Offset     uint64
	Payload    []byte
}

func (f Frame) validate(maxChunk uint32) error {
	if f.ResourceID < 1 || f.ResourceID > 64 {
		return malformed("resource ID out of range")
	}
	if maxChunk < 1 || maxChunk > 65536 {
		return malformed("invalid chunk limit")
	}
	switch f.Type {
	case Request:
		if f.Offset != 0 || len(f.Payload) != 8 {
			return malformed("invalid REQUEST shape")
		}
	case Meta:
		if f.Offset != 0 || len(f.Payload) != 40 {
			return malformed("invalid META shape")
		}
	case Data:
		if len(f.Payload) == 0 || len(f.Payload) > int(maxChunk) {
			return malformed("invalid DATA length")
		}
	case Fin:
		if len(f.Payload) != 0 {
			return malformed("invalid FIN length")
		}
	case Error:
		if f.Offset != 0 || len(f.Payload) < 2 || len(f.Payload) > 258 {
			return malformed("invalid ERROR shape")
		}
	default:
		return malformed("unknown frame type")
	}
	return nil
}

func encodeHeader(f Frame) [HeaderSize]byte {
	var h [HeaderSize]byte
	copy(h[:4], "QB01")
	h[4] = f.Type
	binary.BigEndian.PutUint32(h[8:12], f.ResourceID)
	binary.BigEndian.PutUint64(h[12:20], f.Offset)
	binary.BigEndian.PutUint32(h[20:24], uint32(len(f.Payload)))
	return h
}

func decodeHeader(h [HeaderSize]byte, maxChunk uint32) (Frame, uint32, error) {
	if !bytes.Equal(h[:4], []byte("QB01")) || h[5] != 0 || h[6] != 0 || h[7] != 0 {
		return Frame{}, 0, malformed("bad magic/flags/reserved")
	}
	f := Frame{Type: h[4], ResourceID: binary.BigEndian.Uint32(h[8:12]), Offset: binary.BigEndian.Uint64(h[12:20])}
	n := binary.BigEndian.Uint32(h[20:24])
	// Reject untrusted length before allocation or consuming its body.
	if maxChunk < 1 || maxChunk > 65536 || n > 65536 || f.ResourceID < 1 || f.ResourceID > 64 {
		return Frame{}, 0, malformed("frame exceeds limits")
	}
	switch f.Type {
	case Request:
		if f.Offset != 0 || n != 8 {
			return Frame{}, 0, malformed("invalid REQUEST header")
		}
	case Meta:
		if f.Offset != 0 || n != 40 {
			return Frame{}, 0, malformed("invalid META header")
		}
	case Data:
		if n == 0 || n > maxChunk {
			return Frame{}, 0, malformed("invalid DATA header")
		}
	case Fin:
		if n != 0 {
			return Frame{}, 0, malformed("invalid FIN header")
		}
	case Error:
		if f.Offset != 0 || n < 2 || n > 258 {
			return Frame{}, 0, malformed("invalid ERROR header")
		}
	default:
		return Frame{}, 0, malformed(fmt.Sprintf("unknown frame type %d", f.Type))
	}
	return f, n, nil
}
