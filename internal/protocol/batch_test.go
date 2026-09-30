package protocol

import "testing"

func TestBatchValidation(t *testing.T) {
	batch, err := NewBatch(6, 16384)
	if err != nil {
		t.Fatal(err)
	}
	for _, id := range []uint32{6, 2, 4, 1, 5} {
		f, _ := RequestFrame(id, 6, 16384)
		if err := batch.Register(f); err != nil {
			t.Fatal(err)
		}
	}
	if batch.Complete() {
		t.Fatal("missing sixth request accepted")
	}
	duplicate, _ := RequestFrame(1, 6, 16384)
	if err := batch.Register(duplicate); err == nil {
		t.Fatal("duplicate request accepted")
	}
	wrongCount, _ := RequestFrame(3, 5, 16384)
	if err := batch.Register(wrongCount); err == nil {
		t.Fatal("inconsistent count accepted")
	}
	wrongChunk, _ := RequestFrame(3, 6, 1024)
	if err := batch.Register(wrongChunk); err == nil {
		t.Fatal("inconsistent chunk accepted")
	}
	last, _ := RequestFrame(3, 6, 16384)
	if err := batch.Register(last); err != nil || !batch.Complete() {
		t.Fatalf("complete batch: %v", err)
	}
	if err := batch.Register(last); err == nil {
		t.Fatal("request after barrier accepted")
	}
	if _, err := NewBatch(65, 1); err == nil {
		t.Fatal("oversized batch accepted")
	}
}
