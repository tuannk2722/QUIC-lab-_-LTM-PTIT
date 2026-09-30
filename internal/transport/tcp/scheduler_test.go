package tcp

import (
	"bytes"
	"io"
	"testing"

	"quic-performance-lab/internal/config"
	"quic-performance-lab/internal/protocol"
	"quic-performance-lab/internal/workload"
)

func TestSchedulerTranscriptRoundRobin(t *testing.T) {
	store, err := workload.NewStore(config.Profile{ResourceCount: 6, ResourceSizeBytes: 5, ChunkBytes: 2}, config.Limits{MaxResources: 64, MaxResourceSizeBytes: 16 << 20, MaxTotalBytes: 64 << 20, MaxChunkBytes: 65536})
	if err != nil {
		t.Fatal(err)
	}
	var wire bytes.Buffer
	if err := writeResponses(&wire, store); err != nil {
		t.Fatal(err)
	}
	var got []string
	for {
		f, err := protocol.ReadFrame(&wire, 2)
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		switch f.Type {
		case protocol.Meta:
			got = append(got, "M"+string(rune('0'+f.ResourceID)))
		case protocol.Data:
			got = append(got, "D"+string(rune('0'+f.ResourceID))+string(rune('0'+f.Offset)))
		case protocol.Fin:
			got = append(got, "F"+string(rune('0'+f.ResourceID)))
		default:
			t.Fatalf("unexpected frame %+v", f)
		}
	}
	var want []string
	for id := 1; id <= 6; id++ {
		want = append(want, "M"+string(rune('0'+id)))
	}
	for _, off := range []int{0, 2, 4} {
		for id := 1; id <= 6; id++ {
			want = append(want, "D"+string(rune('0'+id))+string(rune('0'+off)))
			if off == 4 {
				want = append(want, "F"+string(rune('0'+id)))
			}
		}
	}
	if len(got) != len(want) {
		t.Fatalf("frame count %d want %d", len(got), len(want))
	}
	for i := range want {
		if got[i] != want[i] {
			t.Fatalf("frame %d: %s want %s", i, got[i], want[i])
		}
	}
	t.Logf("6 resources; %d frames; META 1..6 then three DATA rounds, FIN immediately after each final DATA", len(got))
}
