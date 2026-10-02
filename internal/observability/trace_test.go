package observability

import (
	"context"
	"crypto/tls"
	"os"
	"path/filepath"
	"testing"

	quicgo "github.com/quic-go/quic-go"
)

func TestExclusiveSecretsAndTraceFlush(t *testing.T) {
	dir := t.TempDir()
	key := filepath.Join(dir, "tls.keylog")
	m, err := New(filepath.Join(dir, "qlog"), key)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := New("", key); err == nil {
		t.Fatal("overwrote secret")
	}
	cfg := &tls.Config{}
	m.TLS(cfg)
	if _, err := cfg.KeyLogWriter.Write([]byte("test-local-secret\n")); err != nil {
		t.Fatal(err)
	}
	qcfg := &quicgo.Config{}
	m.Configure(m.Context(context.Background(), "run", "target"), qcfg)
	trace := qcfg.Tracer(context.Background(), true, quicgo.ConnectionIDFromBytes([]byte{1, 2, 3}))
	producer := trace.AddProducer()
	if err := producer.Close(); err != nil {
		t.Fatal(err)
	}
	if err := m.Close(); err != nil {
		t.Fatal(err)
	}
	st, _ := os.Stat(key)
	if st.Mode().Perm() != 0600 {
		t.Fatal(st.Mode())
	}
	b, err := os.ReadFile(filepath.Join(dir, "qlog", "010203_client.sqlog"))
	if err != nil || len(b) < 100 || b[0] != 0x1e {
		t.Fatalf("trace not flushed %v", err)
	}
	if _, err := New(filepath.Join(dir, "qlog"), ""); err == nil {
		t.Fatal("overwrote mapping")
	}
}
func TestQlogCreateFailureIsVisible(t *testing.T) {
	dir := t.TempDir()
	m, err := New(dir, "")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "01_client.sqlog"), []byte("existing"), 0600); err != nil {
		t.Fatal(err)
	}
	cfg := &quicgo.Config{}
	m.Configure(context.Background(), cfg)
	if cfg.Tracer(context.Background(), true, quicgo.ConnectionIDFromBytes([]byte{1})) != nil {
		t.Fatal("overwrite")
	}
	if m.Close() == nil {
		t.Fatal("lost trace error")
	}
}
