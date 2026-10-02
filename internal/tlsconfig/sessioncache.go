package tlsconfig

import (
	"context"
	"crypto/tls"
	"sync"
)

// TicketCache belongs to one warm-up/target sequence. A non-nil Put, rather
// than a sleep or a successful handshake, signals delivery of a TLS ticket.
type TicketCache struct {
	cache tls.ClientSessionCache
	ready chan struct{}
	once  sync.Once
}

func NewTicketCache() *TicketCache {
	return &TicketCache{cache: tls.NewLRUClientSessionCache(1), ready: make(chan struct{})}
}

func (c *TicketCache) Get(key string) (*tls.ClientSessionState, bool) { return c.cache.Get(key) }

func (c *TicketCache) Put(key string, state *tls.ClientSessionState) {
	c.cache.Put(key, state)
	if state != nil {
		c.once.Do(func() { close(c.ready) })
	}
}

func (c *TicketCache) Wait(ctx context.Context) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-c.ready:
		return nil
	}
}
