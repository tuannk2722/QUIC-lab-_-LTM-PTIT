package metrics

import (
	"math"
	"testing"
	"time"

	"quic-performance-lab/internal/transport"
)

func at(base time.Time, ms int) time.Time { return base.Add(time.Duration(ms) * time.Millisecond) }

func TestSyntheticTimingAndNullability(t *testing.T) {
	base := time.Now()
	a := transport.Timing{Start: base, TCPConnected: at(base, 2), Handshake: at(base, 5), RequestStart: at(base, 6), RequestEnd: at(base, 11), FirstByte: at(base, 9), PayloadDone: at(base, 17), Done: at(base, 18), End: at(base, 40)}
	b := transport.Timing{Start: base, TCPConnected: at(base, 2), Handshake: at(base, 5), RequestStart: at(base, 7), RequestEnd: at(base, 8), FirstByte: at(base, 12), PayloadDone: at(base, 21), Done: at(base, 22), End: at(base, 40)}
	rows := []transport.Result{{ResourceID: 1, BytesExpected: 1000, BytesReceived: 1000, ChecksumOK: true, Timing: a}, {ResourceID: 2, BytesExpected: 1000, BytesReceived: 1000, ChecksumOK: true, Timing: b}}
	r, s, err := Run("tcp", rows, true)
	if err != nil {
		t.Fatal(err)
	}
	assert := func(name string, got *float64, want float64) {
		t.Helper()
		if got == nil || math.Abs(*got-want) > 1e-9 {
			t.Errorf("%s=%v, want %g", name, got, want)
		}
	}
	assert("tcp connect", r.TCPConnectMS, 2)
	assert("TLS handshake", r.TLSHandshakeMS, 3)
	assert("handshake", r.HandshakeMS, 5)
	assert("TTFA", r.TTFAMS, 9)
	assert("transfer", r.TransferMS, 16)
	assert("total excludes hash", r.TotalMS, 22)
	if r.ElapsedMS != 40 {
		t.Errorf("elapsed=%g", r.ElapsedMS)
	}
	assert("goodput", r.GoodputMbps, 1)
	assert("e2e goodput", r.E2EGoodputMbps, 8*2000.0/(22*1000))
	assert("request end can follow first", s[0].RequestEndMS, 11)
	assert("ttfb from request start", s[0].TTFBRequestMS, 3)
	assert("completion from request start", s[1].CompletionRequestMS, 15)
	if r.EarlyReadyMS != nil {
		t.Fatal("cold trial has early-ready metric")
	}
	failed := rows
	failed[1].ChecksumOK = false
	r, _, err = Run("tcp", failed, false)
	if err != nil || r.TotalMS != nil || r.TransferMS != nil || r.GoodputMbps != nil || r.ElapsedMS != 40 {
		t.Fatalf("failed trial metrics: %+v %v", r, err)
	}
	q := rows[:1]
	q[0].Timing.TCPConnected = time.Time{}
	r, _, err = Run("quic", q, true)
	if err != nil || r.TCPConnectMS != nil || r.TLSHandshakeMS != nil {
		t.Fatalf("QUIC nullability: %+v %v", r, err)
	}
}
