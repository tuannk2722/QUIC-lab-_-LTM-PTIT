package quic

import (
	"errors"
	"fmt"
	"io"

	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/workload"

	quicgo "github.com/quic-go/quic-go"
)

const appProtocolError quicgo.ApplicationErrorCode = 1
const streamProtocolError quicgo.StreamErrorCode = 1

// writeResponse owns exactly one stream's send side. No connection-wide lock
// is held during any write, so quic-go schedules independent streams.
func writeResponse(stream *quicgo.Stream, resource workload.Resource, chunk uint32) error {
	if err := protocol.WriteFrame(stream, protocol.MetaFrame(resource.ID(), uint64(resource.Size()), resource.SHA256()), chunk); err != nil {
		return err
	}
	buf := make([]byte, int(chunk))
	for offset := int64(0); offset < resource.Size(); {
		want := min(int64(len(buf)), resource.Size()-offset)
		n, err := resource.ReadAt(buf[:want], offset)
		if err != nil || n != int(want) {
			return fmt.Errorf("resource %d read: n=%d err=%v", resource.ID(), n, err)
		}
		if err := protocol.WriteFrame(stream, protocol.Frame{Type: protocol.Data, ResourceID: resource.ID(), Offset: uint64(offset), Payload: buf[:n]}, chunk); err != nil {
			return err
		}
		offset += int64(n)
	}
	if err := protocol.WriteFrame(stream, protocol.Frame{Type: protocol.Fin, ResourceID: resource.ID(), Offset: uint64(resource.Size())}, chunk); err != nil {
		return err
	}
	return stream.Close() // send-half FIN after the QB01 FIN frame
}

func expectStreamEOF(stream io.Reader) error {
	var extra [1]byte
	n, err := stream.Read(extra[:])
	if n == 0 && errors.Is(err, io.EOF) {
		return nil
	}
	if err != nil && !errors.Is(err, io.EOF) {
		return fmt.Errorf("stream EOF: %w", err)
	}
	return fmt.Errorf("trailing stream data or missing EOF: n=%d", n)
}
