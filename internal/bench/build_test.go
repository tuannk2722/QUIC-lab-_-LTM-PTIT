package bench

import (
	"os"
	"path/filepath"
	"testing"
)

func TestBuildReceiptRejectsSourceAndBinaryReplacement(t *testing.T) {
	for _, mutation := range []string{"none", "source", "added_source", "server", "self"} {
		t.Run(mutation, func(t *testing.T) {
			repo := t.TempDir()
			for _, dir := range []string{"cmd", "internal", "scripts", "bin"} {
				if err := os.Mkdir(filepath.Join(repo, dir), 0700); err != nil {
					t.Fatal(err)
				}
			}
			r := BuildReceipt{SchemaVersion: 1, Inputs: map[string]string{}, Binaries: map[string]string{}}
			put := func(name, value string) {
				t.Helper()
				if err := os.WriteFile(filepath.Join(repo, name), []byte(value), 0600); err != nil {
					t.Fatal(err)
				}
			}
			for _, name := range []string{"go.mod", "go.sum", "Makefile", "scripts/build.py", "cmd/main.go", "internal/code.go"} {
				put(name, "unit fixture")
				r.Inputs[name], _ = HashFile(filepath.Join(repo, name))
			}
			for _, name := range []string{"server", "client", "bench"} {
				put("bin/"+name, "unit "+name)
				r.Binaries[name], _ = executableHash(filepath.Join(repo, "bin", name))
			}
			path := filepath.Join(repo, "build.json")
			if err := WriteJSON(path, r); err != nil {
				t.Fatal(err)
			}
			self := filepath.Join(repo, "bin/bench")
			switch mutation {
			case "source":
				put("internal/code.go", "changed")
			case "added_source":
				put("internal/added.go", "new source")
			case "server":
				put("bin/server", "replacement")
			case "self":
				put("old-bench", "old image")
				self = filepath.Join(repo, "old-bench")
			}
			_, err := verifyBuild(path, repo, self)
			if (err == nil) != (mutation == "none") {
				t.Fatalf("mutation %s: %v", mutation, err)
			}
		})
	}
}
