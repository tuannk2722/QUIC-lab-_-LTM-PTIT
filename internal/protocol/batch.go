package protocol

// Batch validates one QB01 request set. The caller owns synchronization and
// applies the five-second deadline after the first accepted request.
type Batch struct {
	count, chunk uint32
	seen         [65]bool
	received     uint32
}

func NewBatch(count, chunk uint32) (*Batch, error) {
	if count < 1 || count > 64 || chunk < 1 || chunk > 65536 {
		return nil, malformed("invalid batch limits")
	}
	return &Batch{count: count, chunk: chunk}, nil
}

func (b *Batch) Register(f Frame) error {
	if b == nil || b.Complete() {
		return malformed("batch registration closed")
	}
	count, chunk, err := ParseRequest(f)
	if err != nil {
		return err
	}
	if count != b.count || chunk != b.chunk || b.seen[f.ResourceID] {
		return malformed("inconsistent or duplicate batch request")
	}
	b.seen[f.ResourceID] = true
	b.received++
	return nil
}

func (b *Batch) Complete() bool { return b != nil && b.received == b.count }
