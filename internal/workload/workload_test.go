package workload

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"math"
	"sync"
	"testing"

	"quic-performance-lab/internal/config"
)

func limits() config.Limits {
	return config.Limits{MaxResources: 64, MaxResourceSizeBytes: 16 << 20,
		MaxTotalBytes: 64 << 20, MaxChunkBytes: 64 << 10}
}

func TestKnownSmallFixture(t *testing.T) {
	s, err := NewStore(config.Profile{ResourceCount: 2, ResourceSizeBytes: 4, ChunkBytes: 3}, limits())
	if err != nil {
		t.Fatal(err)
	}
	r, err := s.Resource(1)
	if err != nil {
		t.Fatal(err)
	}
	buf := make([]byte, 4)
	if n, err := r.ReadAt(buf, 0); n != 4 || err != nil || !bytes.Equal(buf, []byte{1, 2, 3, 4}) {
		t.Fatalf("fixture bytes: n=%d err=%v bytes=%x", n, err, buf)
	}
	h := r.SHA256()
	if got := hex.EncodeToString(h[:]); got != "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a" {
		t.Fatalf("fixture hash: %s", got)
	}
	r2, _ := s.Resource(2)
	if n, err := r2.ReadAt(buf, 0); n != 4 || err != nil || !bytes.Equal(buf, []byte{2, 3, 4, 5}) {
		t.Fatalf("ID 2 bytes: n=%d err=%v bytes=%x", n, err, buf)
	}
	buf[0] = 99
	if _, err := r.ReadAt(buf[:1], 0); err != nil || buf[0] != 1 {
		t.Fatal("caller mutated store")
	}
	if n, err := r.ReadAt(buf, 2); n != 2 || err != io.EOF || !bytes.Equal(buf[:2], []byte{3, 4}) {
		t.Fatalf("short tail: n=%d err=%v bytes=%x", n, err, buf)
	}
	if _, err := r.ReadAt(buf, -1); err == nil {
		t.Fatal("negative offset accepted")
	}
	if _, err := s.Resource(0); err == nil {
		t.Fatal("zero ID accepted")
	}
	if _, err := s.Resource(3); err == nil {
		t.Fatal("out of range ID accepted")
	}
}

func TestConfiguredProfilesAndSharedStore(t *testing.T) {
	w, err := config.LoadWorkloads("../../configs/workloads.json")
	if err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"bulk", "handshake"} {
		t.Run(name, func(t *testing.T) {
			p := w.Profiles[name]
			a, err := NewStore(p, w.Limits)
			if err != nil {
				t.Fatal(err)
			}
			b, err := NewStore(p, w.Limits)
			if err != nil {
				t.Fatal(err)
			}
			if a.TotalBytes() != p.ResourceCount*p.ResourceSizeBytes || a.Manifest().TotalBytes != a.TotalBytes() {
				t.Fatal("incorrect total")
			}
			if a.Manifest().Count != b.Manifest().Count {
				t.Fatal("different count")
			}
			for id := uint32(1); id <= uint32(a.Count()); id++ {
				r, _ := a.Resource(id)
				other, _ := b.Resource(id)
				buf := make([]byte, r.Size())
				again := make([]byte, r.Size())
				if _, err := r.ReadAt(buf, 0); err != nil {
					t.Fatal(err)
				}
				if _, err := other.ReadAt(again, 0); err != nil || !bytes.Equal(buf, again) {
					t.Fatal("generation differs between instances")
				}
				if sha256.Sum256(buf) != r.SHA256() || r.SHA256() != other.SHA256() {
					t.Fatal("checksum differs")
				}
				for _, off := range []int64{0, 255, r.Size() - 1} {
					if buf[off] != byte((int64(id)+off)%256) {
						t.Fatalf("ID %d offset %d = %d", id, off, buf[off])
					}
				}
			}
			// Both future listeners receive this exact pointer; concurrent readers use no mutable view.
			var wg sync.WaitGroup
			for range 2 {
				wg.Go(func() {
					r, _ := a.Resource(1)
					b := make([]byte, 256)
					if _, err := r.ReadAt(b, 0); err != nil || b[0] != 1 {
						t.Errorf("shared store read: %v", err)
					}
				})
			}
			wg.Wait()
			m, err := json.Marshal(a.Manifest())
			if err != nil {
				t.Fatal(err)
			}
			t.Logf("%s manifest: %s", name, m)
		})
	}
}

func TestRejectBeforeAllocation(t *testing.T) {
	l := limits()
	p := config.Profile{ResourceCount: 1, ResourceSizeBytes: 1, ChunkBytes: 1}
	for name, change := range map[string]func(*config.Profile, *config.Limits){
		"zero count":    func(p *config.Profile, _ *config.Limits) { p.ResourceCount = 0 },
		"count limit":   func(p *config.Profile, _ *config.Limits) { p.ResourceCount = 65 },
		"huge count":    func(p *config.Profile, _ *config.Limits) { p.ResourceCount = math.MaxInt64 },
		"zero size":     func(p *config.Profile, _ *config.Limits) { p.ResourceSizeBytes = 0 },
		"size limit":    func(p *config.Profile, _ *config.Limits) { p.ResourceSizeBytes = 16<<20 + 1 },
		"huge size":     func(p *config.Profile, _ *config.Limits) { p.ResourceSizeBytes = math.MaxInt64 },
		"total limit":   func(p *config.Profile, _ *config.Limits) { p.ResourceCount, p.ResourceSizeBytes = 5, 16<<20 },
		"zero chunk":    func(p *config.Profile, _ *config.Limits) { p.ChunkBytes = 0 },
		"chunk limit":   func(p *config.Profile, _ *config.Limits) { p.ChunkBytes = 64<<10 + 1 },
		"invalid limit": func(_ *config.Profile, l *config.Limits) { l.MaxTotalBytes = math.MaxInt64 },
	} {
		t.Run(name, func(t *testing.T) {
			pp, ll := p, l
			change(&pp, &ll)
			if s, err := NewStore(pp, ll); err == nil || s != nil {
				t.Fatalf("accepted invalid profile %+v limits %+v", pp, ll)
			}
		})
	}
}
