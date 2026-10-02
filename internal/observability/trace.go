// Package observability owns optional, local evidence sinks. Transport writers
// remain independent; this mutex protects only trace bookkeeping and key logs.
package observability

import (
	"bufio"
	"context"
	"crypto/tls"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sync"
	"time"

	quicgo "github.com/quic-go/quic-go"
	"github.com/quic-go/quic-go/qlog"
	"github.com/quic-go/quic-go/qlogwriter"
)

type contextKey struct{}
type scopeKey struct{}
type Scope struct {
	RunID string `json:"run_id"`
	Role  string `json:"role"`
}
type Mapping struct {
	Scope
	ODCID       string `json:"odcid"`
	Perspective string `json:"perspective"`
	Path        string `json:"path"`
	CreatedUTC  string `json:"created_utc"`
}
type Manager struct {
	mu       sync.Mutex
	dir      string
	key      *os.File
	mappings []Mapping
	pending  []<-chan struct{}
	err      error
}

func New(dir, key string) (*Manager, error) {
	m := &Manager{dir: dir}
	if dir != "" {
		if err := os.MkdirAll(dir, 0700); err != nil {
			return nil, err
		}
		// Refuse an existing inventory instead of overwriting previous evidence.
		if _, err := os.Stat(filepath.Join(dir, "mapping.json")); !os.IsNotExist(err) {
			return nil, fmt.Errorf("qlog mapping already exists or is inaccessible")
		}
	}
	if key != "" {
		f, err := os.OpenFile(key, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if err != nil {
			return nil, err
		}
		m.key = f
	}
	return m, nil
}
func (m *Manager) Context(ctx context.Context, runID, role string) context.Context {
	ctx = context.WithValue(ctx, contextKey{}, m)
	return WithScope(ctx, runID, role)
}
func WithScope(ctx context.Context, runID, role string) context.Context {
	return context.WithValue(ctx, scopeKey{}, Scope{runID, role})
}
func Role(ctx context.Context, role string) context.Context {
	s, _ := ctx.Value(scopeKey{}).(Scope)
	return WithScope(ctx, s.RunID, role)
}
func From(ctx context.Context) *Manager { m, _ := ctx.Value(contextKey{}).(*Manager); return m }
func (m *Manager) TLS(cfg *tls.Config) {
	if m.key != nil {
		cfg.KeyLogWriter = m
	}
}
func (m *Manager) Write(p []byte) (int, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	n, err := m.key.Write(p)
	if n != len(p) && err == nil {
		err = io.ErrShortWrite
	}
	m.err = errors.Join(m.err, err)
	return n, err
}
func (m *Manager) Configure(ctx context.Context, cfg *quicgo.Config) {
	if m == nil || m.dir == "" {
		return
	}
	scope, _ := ctx.Value(scopeKey{}).(Scope)
	cfg.Tracer = func(_ context.Context, client bool, id quicgo.ConnectionID) qlogwriter.Trace {
		perspective := "server"
		if client {
			perspective = "client"
		}
		name := id.String() + "_" + perspective + ".sqlog"
		f, err := os.OpenFile(filepath.Join(m.dir, name), os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		m.mu.Lock()
		if err != nil {
			m.err = errors.Join(m.err, err)
			m.mu.Unlock()
			return nil
		}
		done := make(chan struct{})
		sink := &traceSink{file: f, buffer: bufio.NewWriter(f), done: done, manager: m}
		m.pending = append(m.pending, done)
		m.mappings = append(m.mappings, Mapping{scope, id.String(), perspective, name, time.Now().UTC().Format(time.RFC3339Nano)})
		m.mu.Unlock()
		seq := qlogwriter.NewConnectionFileSeq(sink, client, id, []string{qlog.EventSchema})
		go seq.Run()
		return seq
	}
}

type traceSink struct {
	file    *os.File
	buffer  *bufio.Writer
	done    chan struct{}
	manager *Manager
}

func (s *traceSink) Write(p []byte) (int, error) {
	n, err := s.buffer.Write(p)
	if err != nil {
		s.manager.mu.Lock()
		s.manager.err = errors.Join(s.manager.err, err)
		s.manager.mu.Unlock()
	}
	return n, err
}
func (s *traceSink) Close() error {
	err := errors.Join(s.buffer.Flush(), s.file.Close())
	s.manager.mu.Lock()
	s.manager.err = errors.Join(s.manager.err, err)
	s.manager.mu.Unlock()
	close(s.done)
	return err
}

// Close runs after connection/listener shutdown and waits for every qlog writer.
// A timeout is a visible evidence error, never a silently accepted short trace.
func (m *Manager) Close() error {
	m.mu.Lock()
	pending := append([]<-chan struct{}(nil), m.pending...)
	m.mu.Unlock()
	deadline := time.NewTimer(5 * time.Second)
	defer deadline.Stop()
	for _, done := range pending {
		select {
		case <-done:
		case <-deadline.C:
			return fmt.Errorf("qlog flush timeout")
		}
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.key != nil {
		m.err = errors.Join(m.err, m.key.Close())
		m.key = nil
	}
	if m.dir != "" {
		data, err := json.MarshalIndent(map[string]any{"schema_version": 1, "event_schema": qlog.EventSchema, "serialization": "JSON-SEQ", "connections": m.mappings}, "", "  ")
		if err == nil {
			err = os.WriteFile(filepath.Join(m.dir, "mapping.json"), append(data, '\n'), 0600)
		}
		m.err = errors.Join(m.err, err)
	}
	return m.err
}
