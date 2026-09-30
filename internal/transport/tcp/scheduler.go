package tcp

import (
	"fmt"
	"io"

	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/workload"
)

// writeResponses is the sole response writer on the TCP connection. It writes
// all META frames, then at most one DATA frame per live resource per round.
func writeResponses(w io.Writer, store *workload.Store) error {
	if w == nil || store == nil || store.Count() < 1 || store.Count() > 64 {
		return fmt.Errorf("invalid scheduler input")
	}
	chunk := uint32(store.Profile().ChunkBytes)
	resources := make([]workload.Resource, store.Count())
	offsets := make([]int64, store.Count())
	for i := range resources {
		r, err := store.Resource(uint32(i + 1))
		if err != nil {
			return err
		}
		resources[i] = r
		if err := protocol.WriteFrame(w, protocol.MetaFrame(r.ID(), uint64(r.Size()), r.SHA256()), chunk); err != nil {
			return err
		}
	}
	buf := make([]byte, int(chunk))
	for live := len(resources); live > 0; {
		for i, r := range resources {
			if offsets[i] == r.Size() {
				continue
			}
			want := min(int64(len(buf)), r.Size()-offsets[i])
			n, err := r.ReadAt(buf[:want], offsets[i])
			if err != nil || n != int(want) {
				return fmt.Errorf("resource %d read: n=%d err=%v", r.ID(), n, err)
			}
			if err := protocol.WriteFrame(w, protocol.Frame{Type: protocol.Data, ResourceID: r.ID(), Offset: uint64(offsets[i]), Payload: buf[:n]}, chunk); err != nil {
				return err
			}
			offsets[i] += int64(n)
			if offsets[i] == r.Size() {
				if err := protocol.WriteFrame(w, protocol.Frame{Type: protocol.Fin, ResourceID: r.ID(), Offset: uint64(r.Size())}, chunk); err != nil {
					return err
				}
				live--
			}
		}
	}
	return nil
}
