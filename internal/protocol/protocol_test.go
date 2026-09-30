package protocol

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"io"
	"strings"
	"testing"
)

type smallReader struct {
	r    io.Reader
	step int
}

func (s smallReader) Read(p []byte) (int, error) { return s.r.Read(p[:min(len(p), s.step)]) }

type smallWriter struct {
	b          bytes.Buffer
	step       int
	noProgress bool
}

func (s *smallWriter) Write(p []byte) (int, error) {
	if s.noProgress {
		return 0, nil
	}
	return s.b.Write(p[:min(len(p), s.step)])
}

func TestGoldenAndPartialIO(t *testing.T) {
	req, err := RequestFrame(1, 1, 16384)
	if err != nil {
		t.Fatal(err)
	}
	w := &smallWriter{step: 3}
	if err := WriteFrame(w, req, 16384); err != nil {
		t.Fatal(err)
	}
	if got := hex.EncodeToString(w.b.Bytes()[:24]); got != "514230310100000000000001000000000000000000000008" {
		t.Fatalf("golden header %s", got)
	}
	for step := 1; step <= 7; step++ {
		got, err := ReadFrame(smallReader{bytes.NewReader(w.b.Bytes()), step}, 16384)
		if err != nil || got.Type != Request || !bytes.Equal(got.Payload, req.Payload) {
			t.Fatalf("step %d frame=%+v err=%v", step, got, err)
		}
		count, chunk, err := ParseRequest(got)
		if err != nil || count != 1 || chunk != 16384 {
			t.Fatalf("request %d/%d %v", count, chunk, err)
		}
	}
	if err := WriteFrame(&smallWriter{noProgress: true}, req, 16384); !errors.Is(err, ErrNoProgress) {
		t.Fatalf("no-progress %v", err)
	}
	data := Frame{Type: Data, ResourceID: 1, Payload: []byte{1, 2, 3, 4}}
	var wire bytes.Buffer
	if err := WriteFrame(&wire, data, 16384); err != nil {
		t.Fatal(err)
	}
	if err := WriteFrame(&wire, Frame{Type: Fin, ResourceID: 1, Offset: 4}, 16384); err != nil {
		t.Fatal(err)
	}
	reader := smallReader{bytes.NewReader(wire.Bytes()), 2}
	called := 0
	if _, err := ReadFrameObserved(reader, 16384, func() { called++ }); err != nil || called != 1 {
		t.Fatalf("first data hook: count=%d err=%v", called, err)
	}
	if f, err := ReadFrame(reader, 16384); err != nil || f.Type != Fin {
		t.Fatalf("coalesced FIN %+v %v", f, err)
	}
}

func TestMetaAndResponseState(t *testing.T) {
	data := []byte{1, 2, 3, 4}
	hash := sha256.Sum256(data)
	m := MetaFrame(1, 4, hash)
	var wire bytes.Buffer
	if err := WriteFrame(&wire, m, 4); err != nil {
		t.Fatal(err)
	}
	parsed, err := ReadFrame(&wire, 4)
	if err != nil {
		t.Fatal(err)
	}
	size, h, err := ParseMeta(parsed)
	if err != nil || size != 4 || h != hash || len(parsed.Payload) != 40 {
		t.Fatalf("META size/hash/raw %d %x %v", size, h, err)
	}
	newReceiver := func() *Receiver {
		r, err := NewReceiver(1, 4, hash, 4)
		if err != nil {
			t.Fatal(err)
		}
		return r
	}
	r := newReceiver()
	if err := r.Accept(parsed); err != nil {
		t.Fatal(err)
	}
	if err := r.Accept(Frame{Type: Data, ResourceID: 1, Offset: 0, Payload: data[:2]}); err != nil {
		t.Fatal(err)
	}
	if err := r.Accept(Frame{Type: Data, ResourceID: 1, Offset: 2, Payload: data[2:]}); err != nil {
		t.Fatal(err)
	}
	if err := r.Accept(Frame{Type: Fin, ResourceID: 1, Offset: 4}); err != nil || !r.Complete() {
		t.Fatalf("FIN %v", err)
	}
	if err := r.Verify(); err != nil {
		t.Fatal(err)
	}
	if err := r.Accept(Frame{Type: Fin, ResourceID: 1, Offset: 4}); err == nil {
		t.Fatal("duplicate FIN accepted")
	}
	for name, frames := range map[string][]Frame{
		"missing META":     {{Type: Data, ResourceID: 1, Payload: data}},
		"wrong ID":         {m, {Type: Data, ResourceID: 2, Payload: data}},
		"duplicate META":   {m, m},
		"wrong offset":     {m, {Type: Data, ResourceID: 1, Offset: 1, Payload: data}},
		"overflow":         {m, {Type: Data, ResourceID: 1, Payload: []byte{1, 2, 3, 4, 5}}},
		"early FIN":        {m, {Type: Fin, ResourceID: 1, Offset: 4}},
		"wrong FIN offset": {m, {Type: Data, ResourceID: 1, Payload: data}, {Type: Fin, ResourceID: 1, Offset: 3}},
	} {
		t.Run(name, func(t *testing.T) {
			r := newReceiver()
			var err error
			for _, f := range frames {
				err = r.Accept(f)
				if err != nil {
					break
				}
			}
			if err == nil {
				t.Fatal("accepted invalid response")
			}
		})
	}
	if err := newReceiver().Verify(); err == nil {
		t.Fatal("EOF before FIN accepted")
	}
	corrupt := newReceiver()
	for _, f := range []Frame{m, {Type: Data, ResourceID: 1, Payload: []byte{9, 2, 3, 4}}, {Type: Fin, ResourceID: 1, Offset: 4}} {
		if err := corrupt.Accept(f); err != nil {
			t.Fatal(err)
		}
	}
	if err := corrupt.Verify(); err == nil {
		t.Fatal("corrupt payload accepted")
	}
}

func TestErrorFrameRoundtrip(t *testing.T) {
	e, err := ErrorFrame(1, CodeInvalidBatch, "wrong count")
	if err != nil {
		t.Fatal(err)
	}
	var wire bytes.Buffer
	if err := WriteFrame(&wire, e, 1024); err != nil {
		t.Fatal(err)
	}
	got, err := ReadFrame(&wire, 1024)
	if err != nil {
		t.Fatal(err)
	}
	code, message, err := ParseError(got)
	if err != nil || code != CodeInvalidBatch || message != "wrong count" {
		t.Fatalf("ERROR %d %q %v", code, message, err)
	}
	if _, _, err := ParseError(Frame{Type: Error, ResourceID: 1, Payload: []byte{0, 1, 0xff}}); err == nil {
		t.Fatal("invalid UTF-8 accepted")
	}
}

func TestMalformedHeadersAndTruncation(t *testing.T) {
	req, _ := RequestFrame(1, 1, 16)
	var b bytes.Buffer
	if err := WriteFrame(&b, req, 16); err != nil {
		t.Fatal(err)
	}
	valid := b.Bytes()
	for name, change := range map[string]func([]byte){
		"magic":       func(b []byte) { b[0] = 0 },
		"type":        func(b []byte) { b[4] = 9 },
		"flags":       func(b []byte) { b[5] = 1 },
		"reserved":    func(b []byte) { b[7] = 1 },
		"id":          func(b []byte) { b[11] = 0 },
		"offset":      func(b []byte) { b[19] = 1 },
		"bad length":  func(b []byte) { b[23] = 9 },
		"huge length": func(b []byte) { b[20] = 0xff; b[21] = 0xff; b[22] = 0xff; b[23] = 0xff },
	} {
		t.Run(name, func(t *testing.T) {
			copyOf := append([]byte{}, valid...)
			change(copyOf)
			if _, err := ReadFrame(bytes.NewReader(copyOf), 16); err == nil {
				t.Fatal("accepted malformed header")
			}
		})
	}
	for n := 0; n < len(valid); n++ {
		if _, err := ReadFrame(bytes.NewReader(valid[:n]), 16); err == nil {
			t.Fatalf("accepted truncated frame at %d", n)
		}
	}
	if _, err := RequestFrame(1, 0, 16); err == nil {
		t.Fatal("count zero")
	}
	if _, err := RequestFrame(1, 65, 16); err == nil {
		t.Fatal("count 65")
	}
	if _, err := RequestFrame(1, 1, 0); err == nil {
		t.Fatal("chunk zero")
	}
	if _, err := RequestFrame(1, 1, 65537); err == nil {
		t.Fatal("chunk 65537")
	}
	if _, err := ErrorFrame(1, CodeMalformed, strings.Repeat("x", 257)); err == nil {
		t.Fatal("oversized ERROR")
	}
}

func FuzzReadFrame(f *testing.F) {
	req, _ := RequestFrame(1, 1, 16)
	var b bytes.Buffer
	_ = WriteFrame(&b, req, 16)
	f.Add(b.Bytes())
	f.Add([]byte("QB01"))
	f.Add(bytes.Repeat([]byte{0xff}, 24))
	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 2048 {
			t.Skip()
		}
		_, _ = ReadFrame(bytes.NewReader(data), 16)
	})
}
