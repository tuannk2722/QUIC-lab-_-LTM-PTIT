package transport

import (
	"crypto/tls"
	"fmt"
	"syscall"
)

// ConnectionInfo is sidecar metadata sampled during cleanup, after FIN. It
// does not extend the canonical schema or add logs to the transfer data path.
type ConnectionInfo struct {
	TLSVersion         string `json:"tls_version"`
	CipherSuite        string `json:"cipher_suite"`
	ALPN               string `json:"alpn"`
	DidResume          bool   `json:"did_resume"`
	QUICVersion        string `json:"quic_version"`
	Used0RTT           *bool  `json:"used_0rtt"`
	SendBufferBytes    *int   `json:"send_buffer_bytes"`
	ReceiveBufferBytes *int   `json:"receive_buffer_bytes"`
	BufferError        string `json:"buffer_error"`
}

func ObserveConnection(s tls.ConnectionState, socket any) *ConnectionInfo {
	i := &ConnectionInfo{TLSVersion: tls.VersionName(s.Version), CipherSuite: tls.CipherSuiteName(s.CipherSuite), ALPN: s.NegotiatedProtocol, DidResume: s.DidResume}
	c, ok := socket.(syscall.Conn)
	if !ok {
		i.BufferError = "unknown: socket does not expose SyscallConn"
		return i
	}
	raw, err := c.SyscallConn()
	if err != nil {
		i.BufferError = err.Error()
		return i
	}
	err = raw.Control(func(fd uintptr) {
		for _, item := range []struct {
			opt int
			dst **int
		}{{syscall.SO_SNDBUF, &i.SendBufferBytes}, {syscall.SO_RCVBUF, &i.ReceiveBufferBytes}} {
			v, err := syscall.GetsockoptInt(int(fd), syscall.SOL_SOCKET, item.opt)
			if err != nil {
				i.BufferError = fmt.Sprint(err)
				continue
			}
			*item.dst = &v
		}
	})
	if err != nil {
		i.BufferError = err.Error()
	}
	return i
}
