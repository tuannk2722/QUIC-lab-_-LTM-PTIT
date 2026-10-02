package transport

import (
	"testing"
	"time"
)

func TestBoundedProgressThresholdAndFinal(t *testing.T) {
	r := Result{BytesExpected: 65537}
	PrepareProgress(&r, true)
	r.Timing.Start = time.Now()
	for _, n := range []uint64{8192, 32768, 65536, 65537} {
		RecordProgress(&r, n)
	}
	if len(r.Progress) != 5 || cap(r.Progress) != 5 {
		t.Fatalf("points/cap=%d/%d", len(r.Progress), cap(r.Progress))
	}
	for i, p := range r.Progress {
		want := uint64((i + 1) * 16384)
		if i == 4 {
			want = 65537
		}
		if p.Bytes != want || p.ElapsedMS < 0 {
			t.Fatal(p)
		}
	}
	disabled := Result{BytesExpected: 1}
	PrepareProgress(&disabled, false)
	RecordProgress(&disabled, 1)
	if disabled.Progress != nil {
		t.Fatal("performance instrumentation")
	}
}
