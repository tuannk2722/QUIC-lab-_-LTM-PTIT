package workload

import (
	"crypto/sha256"
	"fmt"

	"quic-performance-lab/internal/config"
)

// NewStore validates every size and multiplication before allocating any resource.
// A single Store can be shared by the TCP and QUIC listeners without synchronization.
func NewStore(p config.Profile, l config.Limits) (*Store, error) {
	if l.MaxResources < 1 || l.MaxResources > 64 ||
		l.MaxResourceSizeBytes < 1 || l.MaxResourceSizeBytes > 16<<20 ||
		l.MaxTotalBytes < 1 || l.MaxTotalBytes > 64<<20 ||
		l.MaxChunkBytes < 1 || l.MaxChunkBytes > 64<<10 {
		return nil, fmt.Errorf("invalid workload limits")
	}
	if p.ResourceCount < 1 || p.ResourceCount > l.MaxResources ||
		p.ResourceSizeBytes < 1 || p.ResourceSizeBytes > l.MaxResourceSizeBytes ||
		p.ChunkBytes < 1 || p.ChunkBytes > l.MaxChunkBytes ||
		p.ResourceSizeBytes > l.MaxTotalBytes/p.ResourceCount {
		return nil, fmt.Errorf("profile exceeds workload limits")
	}
	// The caps above also make int conversion safe on 32-bit Go platforms.
	s := &Store{profile: p, total: p.ResourceCount * p.ResourceSizeBytes,
		resources: make([]Resource, int(p.ResourceCount))}
	for i := range s.resources {
		id := uint32(i + 1)
		data := make([]byte, int(p.ResourceSizeBytes))
		for j := range data {
			data[j] = byte((uint64(id) + uint64(j)) % 256)
		}
		s.resources[i] = Resource{id: id, data: data, hash: sha256.Sum256(data)}
	}
	return s, nil
}
