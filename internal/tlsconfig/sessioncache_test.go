package tlsconfig

import (
	"context"
	"crypto/tls"
	"errors"
	"sync"
	"testing"
	"time"
)

func TestTicketCacheNotificationCancellationAndConcurrency(t *testing.T) {
	c := NewTicketCache()
	c.Put("server", nil)
	ctx, stop := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer stop()
	if !errors.Is(c.Wait(ctx), context.DeadlineExceeded) {
		t.Fatal("nil Put signalled a ticket")
	}
	var wg sync.WaitGroup
	for range 20 {
		wg.Go(func() { c.Put("server", &tls.ClientSessionState{}); c.Get("server") })
	}
	wg.Wait()
	if err := c.Wait(context.Background()); err != nil {
		t.Fatal(err)
	}
	if _, ok := c.Get("server"); !ok {
		t.Fatal("ticket not cached")
	}
	cancelled, cancel := context.WithCancel(context.Background())
	cancel()
	if !errors.Is(NewTicketCache().Wait(cancelled), context.Canceled) {
		t.Fatal("Wait ignored cancellation")
	}
}
