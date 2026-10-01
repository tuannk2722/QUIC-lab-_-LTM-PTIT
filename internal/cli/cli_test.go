package cli

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"
)

func TestCommandContract(t *testing.T) {
	for _, name := range []string{"server", "client", "bench"} {
		t.Run(name, func(t *testing.T) {
			for _, tc := range []struct {
				args []string
				code int
			}{
				{[]string{"--help"}, 0}, {[]string{"--version"}, 0},
				{[]string{"--unknown"}, 2}, {[]string{"extra"}, 2},
				{[]string{"--profiles=/nonexistent"}, 2},
			} {
				var out, errs bytes.Buffer
				if code := Run(name, tc.args, &out, &errs); code != tc.code {
					t.Fatalf("%v: %d %s", tc.args, code, errs.String())
				}
			}
			base := []string{"--profiles=../../configs/workloads.json"}
			if name == "server" {
				base = append(base, "--cert=/nonexistent")
			}
			if name == "client" {
				base = append(base, "--transport=quic", "--ca=/nonexistent")
			}
			if name == "bench" {
				base = append(base, "--scenarios=../../configs/scenarios.json", "--ca=/nonexistent")
			}
			var out, errs bytes.Buffer
			if code := Run(name, base, &out, &errs); code != 1 || out.Len() != 0 {
				t.Fatalf("fake success: %d %s %s", code, &out, &errs)
			}
			cases := [][]string{{"--transport=http3"}, {"--profile=missing"}}
			if name == "client" {
				cases = append(cases, []string{"--network-state=/nonexistent"})
			}
			if name == "server" {
				cases = append(cases, []string{"--listen=localhost:0"}, []string{"--cert="})
			} else {
				cases = append(cases, []string{"--addr=bad"}, []string{"--transport=tcp", "--mode=early"}, []string{"--transport=tcp", "--mode=resumed"}, []string{"--timeout=0s"}, []string{"--timeout=-1s"}, []string{"--format=csv"}, []string{"--ca="}, []string{"--experiment-id=../bad"}, []string{"--run-id=../bad"})
			}
			if name == "bench" {
				cases = append(cases, []string{"--runs=0"}, []string{"--warmups=-1"}, []string{"--scenario=missing"}, []string{"--plan", "--merge=x"})
			}
			for _, args := range cases {
				var o, e bytes.Buffer
				if code := Run(name, append(append([]string{}, base...), args...), &o, &e); code != 2 {
					t.Errorf("%v: code=%d %s", args, code, &e)
				}
			}
		})
	}
}

func TestReadyFileKeepsExistingOwner(t *testing.T) {
	path := filepath.Join(t.TempDir(), "ready")
	if err := os.WriteFile(path, []byte("other server\n"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := writeReadyFile(path, "new server\n"); err == nil {
		t.Fatal("overwrote another server's ready file")
	}
	data, err := os.ReadFile(path)
	if err != nil || string(data) != "other server\n" {
		t.Fatalf("existing ready file changed: %q %v", data, err)
	}
	newPath := filepath.Join(t.TempDir(), "ready")
	if err := writeReadyFile(newPath, "new server\n"); err != nil {
		t.Fatal(err)
	}
	data, err = os.ReadFile(newPath)
	if err != nil || string(data) != "new server\n" {
		t.Fatalf("ready file incomplete: %q %v", data, err)
	}
}
