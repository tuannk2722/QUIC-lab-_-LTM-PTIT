package cli

import (
	"bytes"
	"strings"
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
			if name == "client" {
				base = append(base, "--transport=quic")
			}
			if name == "bench" {
				base = append(base, "--scenarios=../../configs/scenarios.json")
			}
			var out, errs bytes.Buffer
			if code := Run(name, base, &out, &errs); code != 1 || out.Len() != 0 || !strings.Contains(errs.String(), "not implemented") {
				t.Fatalf("fake success: %d %s %s", code, &out, &errs)
			}
			cases := [][]string{{"--transport=http3"}, {"--profile=missing"}}
			if name == "server" {
				cases = append(cases, []string{"--listen=localhost:0"}, []string{"--cert="})
			} else {
				cases = append(cases, []string{"--addr=bad"}, []string{"--transport=tcp", "--mode=early"}, []string{"--transport=tcp", "--mode=resumed"}, []string{"--timeout=0s"}, []string{"--timeout=-1s"}, []string{"--format=csv"}, []string{"--ca="})
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
