package protocol

import (
	"crypto/sha256"
	"fmt"
)

// Receiver enforces the per-resource META, DATA*, FIN state machine.
type Receiver struct {
	id           uint32
	expectedSize uint64
	expectedHash [sha256.Size]byte
	chunk        uint32
	buf          []byte
	meta, fin    bool
	next         uint64
}

func NewReceiver(id uint32, size uint64, hash [sha256.Size]byte, chunk uint32) (*Receiver, error) {
	if id < 1 || id > 64 || size < 1 || size > 16<<20 || chunk < 1 || chunk > 65536 {
		return nil, malformed("invalid receiver limits")
	}
	return &Receiver{id: id, expectedSize: size, expectedHash: hash, chunk: chunk, buf: make([]byte, int(size))}, nil
}

func (r *Receiver) Accept(f Frame) error {
	if err := f.validate(r.chunk); err != nil {
		return err
	}
	if f.ResourceID != r.id {
		return malformed("wrong response resource ID")
	}
	if r.fin {
		return malformed("frame after FIN")
	}
	if f.Type == Error {
		code, message, err := ParseError(f)
		if err != nil {
			return err
		}
		return fmt.Errorf("server ERROR %d: %s", code, message)
	}
	if !r.meta {
		if f.Type != Meta {
			return malformed("META required first")
		}
		size, hash, err := ParseMeta(f)
		if err != nil {
			return err
		}
		if size != r.expectedSize || hash != r.expectedHash {
			return malformed("META differs from expected workload")
		}
		r.meta = true
		return nil
	}
	switch f.Type {
	case Data:
		if f.Offset != r.next || uint64(len(f.Payload)) > r.expectedSize-r.next {
			return malformed("DATA offset/size mismatch")
		}
		copy(r.buf[r.next:], f.Payload)
		r.next += uint64(len(f.Payload))
	case Fin:
		if f.Offset != r.expectedSize || r.next != r.expectedSize {
			return malformed("FIN before complete payload")
		}
		r.fin = true
	default:
		return malformed("unexpected response frame")
	}
	return nil
}

func (r *Receiver) Complete() bool        { return r.fin }
func (r *Receiver) BytesReceived() uint64 { return r.next }
func (r *Receiver) Verify() error {
	if !r.fin {
		return malformed("EOF before FIN")
	}
	if sha256.Sum256(r.buf) != r.expectedHash {
		return malformed("checksum mismatch")
	}
	return nil
}
