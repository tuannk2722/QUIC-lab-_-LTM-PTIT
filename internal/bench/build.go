package bench

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"strings"

	"quic-performance-lab/internal/config"
)

type BuildReceipt struct {
	SchemaVersion int               `json:"schema_version"`
	Inputs        map[string]string `json:"inputs"`
	Binaries      map[string]string `json:"binaries"`
	GoVersion     string            `json:"go_version"`
	BuildFlags    []string          `json:"build_flags"`
}

func executableHash(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// VerifyBuild rejects stale source, replaced binaries and an already-running
// old bench image. /proc/self/exe identifies the image even after path replace.
func VerifyBuild(path string) (BuildReceipt, error) {
	return verifyBuild(path, ".", "/proc/self/exe")
}

func verifyBuild(path, repo, executable string) (BuildReceipt, error) {
	var receipt BuildReceipt
	if err := config.DecodeJSON(path, &receipt, config.MaxConfigBytes); err != nil {
		return receipt, fmt.Errorf("build receipt unavailable; run make build: %w", err)
	}
	inputs := map[string]string{}
	add := func(path string) error {
		h, err := HashFile(filepath.Join(repo, path))
		if err == nil {
			inputs[path] = h
		}
		return err
	}
	for _, path := range []string{"go.mod", "go.sum", "Makefile", "scripts/build.py"} {
		if err := add(path); err != nil {
			return receipt, err
		}
	}
	for _, dir := range []string{"cmd", "internal"} {
		if err := filepath.WalkDir(filepath.Join(repo, dir), func(path string, d os.DirEntry, err error) error {
			if err != nil {
				return err
			}
			if !d.IsDir() && strings.HasSuffix(path, ".go") && !strings.HasSuffix(path, "_test.go") {
				relative, err := filepath.Rel(repo, path)
				if err != nil {
					return err
				}
				return add(relative)
			}
			return nil
		}); err != nil {
			return receipt, err
		}
	}
	if receipt.SchemaVersion != 1 || !reflect.DeepEqual(receipt.Inputs, inputs) || len(receipt.Binaries) != 3 {
		return receipt, fmt.Errorf("build inputs changed or receipt invalid; run make build")
	}
	for _, name := range []string{"server", "client", "bench"} {
		h, err := executableHash(filepath.Join(repo, "bin", name))
		if err != nil || h != receipt.Binaries[name] {
			return receipt, fmt.Errorf("build binary changed: %s; run make build", name)
		}
	}
	h, err := executableHash(executable)
	if err != nil || h != receipt.Binaries["bench"] {
		return receipt, fmt.Errorf("running bench differs from build receipt")
	}
	return receipt, nil
}
