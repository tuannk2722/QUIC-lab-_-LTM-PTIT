package protocol

import (
	"errors"
	"io"
)

var ErrNoProgress = errors.New("writer made no progress")

func WriteAll(w io.Writer, p []byte) error {
	for len(p) > 0 {
		n, err := w.Write(p)
		if n < 0 || n > len(p) {
			return errors.New("writer returned invalid count")
		}
		p = p[n:]
		if err != nil {
			return err
		}
		if n == 0 {
			return ErrNoProgress
		}
	}
	return nil
}

func WriteFrame(w io.Writer, f Frame, maxChunk uint32) error {
	if err := f.validate(maxChunk); err != nil {
		return err
	}
	h := encodeHeader(f)
	if err := WriteAll(w, h[:]); err != nil {
		return err
	}
	return WriteAll(w, f.Payload)
}

func ReadFrame(r io.Reader, maxChunk uint32) (Frame, error) {
	return ReadFrameObserved(r, maxChunk, nil)
}

// onFirstDataRead runs on the first successful read of DATA payload, before its
// remaining bytes arrive. It is intended for the client's first-byte timestamp.
func ReadFrameObserved(r io.Reader, maxChunk uint32, onFirstDataRead func()) (Frame, error) {
	return ReadFrameObservedID(r, maxChunk, func(uint32) {
		if onFirstDataRead != nil {
			onFirstDataRead()
		}
	})
}

// ReadFrameObservedID identifies the DATA resource when its first payload byte
// is read; the callback runs before the rest of that frame has arrived.
func ReadFrameObservedID(r io.Reader, maxChunk uint32, onFirstDataRead func(uint32)) (Frame, error) {
	var h [HeaderSize]byte
	if _, err := io.ReadFull(r, h[:]); err != nil {
		return Frame{}, err
	}
	f, n, err := decodeHeader(h, maxChunk)
	if err != nil {
		return Frame{}, err
	}
	f.Payload = make([]byte, int(n))
	if f.Type != Data {
		_, err = io.ReadFull(r, f.Payload)
		return f, err
	}
	for off := 0; off < len(f.Payload); {
		read, readErr := r.Read(f.Payload[off:])
		if read < 0 || read > len(f.Payload)-off {
			return Frame{}, malformed("reader returned invalid count")
		}
		if read > 0 && off == 0 && onFirstDataRead != nil {
			onFirstDataRead(f.ResourceID)
		}
		off += read
		if readErr != nil {
			if off == len(f.Payload) && readErr == io.EOF {
				return f, nil
			}
			return Frame{}, readErr
		}
		if read == 0 {
			return Frame{}, io.ErrNoProgress
		}
	}
	return f, nil
}
