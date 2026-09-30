// Package tlsconfig establishes the common TLS identity policy; it opens no sockets.
package tlsconfig

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"os"
)

const ALPN = "quicbench/1"

func Server(certFile, keyFile string) (*tls.Config, error) {
	cert, err := tls.LoadX509KeyPair(certFile, keyFile)
	if err != nil {
		return nil, err
	}
	return &tls.Config{MinVersion: tls.VersionTLS13, MaxVersion: tls.VersionTLS13, NextProtos: []string{ALPN}, Certificates: []tls.Certificate{cert}}, nil
}

func Client(caFile, serverName string) (*tls.Config, error) {
	if serverName == "" {
		return nil, fmt.Errorf("server name is required")
	}
	pem, err := os.ReadFile(caFile)
	if err != nil {
		return nil, err
	}
	roots := x509.NewCertPool()
	if !roots.AppendCertsFromPEM(pem) {
		return nil, fmt.Errorf("CA file contains no certificates")
	}
	return &tls.Config{MinVersion: tls.VersionTLS13, MaxVersion: tls.VersionTLS13, NextProtos: []string{ALPN}, RootCAs: roots, ServerName: serverName}, nil
}
