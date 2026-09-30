// Package workload owns deterministic, immutable resource data for both transports.
package workload

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"

	"quic-performance-lab/internal/config"
)

// Resource never exposes its backing slice. Callers can read it concurrently.
type Resource struct {
	id   uint32
	data []byte
	hash [sha256.Size]byte
}

func (r Resource) ID() uint32                { return r.id }
func (r Resource) Size() int64               { return int64(len(r.data)) }
func (r Resource) SHA256() [sha256.Size]byte { return r.hash }

// ReadAt follows io.ReaderAt and copies bytes into the caller's buffer.
func (r Resource) ReadAt(p []byte, off int64) (int, error) {
	if off < 0 {
		return 0, fmt.Errorf("negative resource offset")
	}
	if off >= int64(len(r.data)) {
		if len(p) == 0 {
			return 0, nil
		}
		return 0, io.EOF
	}
	n := copy(p, r.data[off:])
	if n < len(p) {
		return n, io.EOF
	}
	return n, nil
}

type Store struct {
	profile   config.Profile
	resources []Resource
	total     int64
}

func (s *Store) Count() int              { return len(s.resources) }
func (s *Store) TotalBytes() int64       { return s.total }
func (s *Store) Profile() config.Profile { return s.profile }
func (s *Store) Resource(id uint32) (Resource, error) {
	if id == 0 || uint64(id) > uint64(len(s.resources)) {
		return Resource{}, fmt.Errorf("unknown resource %d", id)
	}
	return s.resources[id-1], nil
}

type ResourceInfo struct {
	ID        uint32 `json:"resource_id"`
	SizeBytes int64  `json:"size_bytes"`
	SHA256Hex string `json:"sha256"`
}

type Manifest struct {
	Generator  string         `json:"generator"`
	Checksum   string         `json:"checksum"`
	Count      int            `json:"resource_count"`
	TotalBytes int64          `json:"total_bytes"`
	ChunkBytes int64          `json:"chunk_bytes"`
	Resources  []ResourceInfo `json:"resources"`
}

// Manifest returns detached values usable as client expectations or evidence.
func (s *Store) Manifest() Manifest {
	m := Manifest{
		Generator: "byte((resource_id + offset) % 256)", Checksum: "sha256",
		Count: len(s.resources), TotalBytes: s.total, ChunkBytes: s.profile.ChunkBytes,
		Resources: make([]ResourceInfo, len(s.resources)),
	}
	for i := range s.resources {
		r := &s.resources[i]
		m.Resources[i] = ResourceInfo{ID: r.id, SizeBytes: int64(len(r.data)), SHA256Hex: hex.EncodeToString(r.hash[:])}
	}
	return m
}
