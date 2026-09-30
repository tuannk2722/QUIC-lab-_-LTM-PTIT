package tlsconfig

import (
	"crypto/tls"
	"crypto/x509"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestGeneratedIdentity(t *testing.T) {
	dir := t.TempDir()
	generate := func(args ...string) error {
		c := exec.Command("bash", append([]string{"../../scripts/gen-cert.sh", "--dir", dir}, args...)...)
		b, err := c.CombinedOutput()
		t.Logf("cert script: %s", b)
		return err
	}
	if err := generate(); err != nil {
		t.Fatal(err)
	}
	cert, key := filepath.Join(dir, "server.crt"), filepath.Join(dir, "server.key")
	before, err := os.ReadFile(key)
	if err != nil {
		t.Fatal(err)
	}
	if err := generate(); err == nil {
		t.Fatal("overwrote existing identity without --force")
	}
	after, err := os.ReadFile(key)
	if err != nil {
		t.Fatal(err)
	}
	if string(before) != string(after) {
		t.Fatal("changed protected key")
	}
	info, err := os.Stat(key)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0600 {
		t.Fatalf("key mode %v", info.Mode())
	}
	s, err := Server(cert, key)
	if err != nil {
		t.Fatal(err)
	}
	leaf, err := x509.ParseCertificate(s.Certificates[0].Certificate[0])
	if err != nil {
		t.Fatal(err)
	}
	for _, name := range []string{"localhost", "127.0.0.1", "10.10.0.2"} {
		c, err := Client(cert, name)
		if err != nil {
			t.Fatal(err)
		}
		if c.InsecureSkipVerify || c.MinVersion != tls.VersionTLS13 || c.MaxVersion != tls.VersionTLS13 || c.NextProtos[0] != ALPN {
			t.Fatal("unsafe client TLS policy")
		}
		if _, err := leaf.Verify(x509.VerifyOptions{Roots: c.RootCAs, DNSName: name}); err != nil {
			t.Fatal(err)
		}
	}
	if s.MinVersion != tls.VersionTLS13 || s.MaxVersion != tls.VersionTLS13 || s.NextProtos[0] != ALPN {
		t.Fatal("wrong server policy")
	}
	if _, err := leaf.Verify(x509.VerifyOptions{Roots: x509.NewCertPool(), DNSName: "localhost"}); err == nil {
		t.Fatal("untrusted certificate accepted")
	}
	c, _ := Client(cert, "wrong.example")
	if _, err := leaf.Verify(x509.VerifyOptions{Roots: c.RootCAs, DNSName: c.ServerName}); err == nil {
		t.Fatal("wrong SAN accepted")
	}
	if _, err := Client(key, "localhost"); err == nil {
		t.Fatal("private key accepted as CA")
	}
	if _, err := Client(cert, ""); err == nil {
		t.Fatal("empty server name accepted")
	}
	if err := generate("--force"); err != nil {
		t.Fatal(err)
	}
	if _, err := Server(cert, key); err != nil {
		t.Fatal("forced replacement has mismatched identity", err)
	}
}
