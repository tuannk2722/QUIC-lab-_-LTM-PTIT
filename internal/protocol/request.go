package protocol

import (
	"crypto/sha256"
	"encoding/binary"
)

func RequestFrame(id, count, chunk uint32) (Frame, error) {
	if count < 1 || count > 64 || id < 1 || id > count || chunk < 1 || chunk > 65536 {
		return Frame{}, malformed("invalid request values")
	}
	p := make([]byte, 8)
	binary.BigEndian.PutUint32(p[:4], count)
	binary.BigEndian.PutUint32(p[4:], chunk)
	return Frame{Type: Request, ResourceID: id, Payload: p}, nil
}

func ParseRequest(f Frame) (count, chunk uint32, err error) {
	if f.Type != Request || f.validate(65536) != nil {
		return 0, 0, malformed("not REQUEST")
	}
	count, chunk = binary.BigEndian.Uint32(f.Payload[:4]), binary.BigEndian.Uint32(f.Payload[4:])
	if count < 1 || count > 64 || f.ResourceID > count || chunk < 1 || chunk > 65536 {
		return 0, 0, malformed("invalid request values")
	}
	return count, chunk, nil
}

func MetaFrame(id uint32, size uint64, hash [sha256.Size]byte) Frame {
	p := make([]byte, 40)
	binary.BigEndian.PutUint64(p[:8], size)
	copy(p[8:], hash[:])
	return Frame{Type: Meta, ResourceID: id, Payload: p}
}

func ParseMeta(f Frame) (uint64, [sha256.Size]byte, error) {
	var hash [sha256.Size]byte
	if f.Type != Meta || f.validate(65536) != nil {
		return 0, hash, malformed("not META")
	}
	size := binary.BigEndian.Uint64(f.Payload[:8])
	copy(hash[:], f.Payload[8:])
	if size < 1 || size > 16<<20 {
		return 0, hash, malformed("invalid META size")
	}
	return size, hash, nil
}
