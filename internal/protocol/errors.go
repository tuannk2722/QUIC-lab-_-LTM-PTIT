package protocol

import (
	"errors"
	"fmt"
	"unicode/utf8"

	"encoding/binary"
)

var ErrMalformed = errors.New("malformed QB01 frame")

func malformed(s string) error { return fmt.Errorf("%w: %s", ErrMalformed, s) }

const (
	CodeMalformed       uint16 = 1
	CodeUnknownResource uint16 = 2
	CodeInvalidBatch    uint16 = 3
	CodeLimitExceeded   uint16 = 4
	CodeInternal        uint16 = 5
	CodeBatchTimeout    uint16 = 6
)

func ErrorFrame(id uint32, code uint16, message string) (Frame, error) {
	if code < 1 || code > 6 || !utf8.ValidString(message) || len(message) > 256 {
		return Frame{}, malformed("invalid error code/message")
	}
	p := make([]byte, 2+len(message))
	binary.BigEndian.PutUint16(p[:2], code)
	copy(p[2:], message)
	return Frame{Type: Error, ResourceID: id, Payload: p}, nil
}

func ParseError(f Frame) (uint16, string, error) {
	if f.Type != Error || f.validate(65536) != nil {
		return 0, "", malformed("not ERROR")
	}
	code := binary.BigEndian.Uint16(f.Payload[:2])
	message := string(f.Payload[2:])
	if code < 1 || code > 6 || !utf8.ValidString(message) {
		return 0, "", malformed("invalid ERROR payload")
	}
	return code, message, nil
}
