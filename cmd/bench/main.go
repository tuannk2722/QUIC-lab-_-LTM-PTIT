package main

import (
	"os"
	"quic-performance-lab/internal/cli"
)

func main() { os.Exit(cli.Run("bench", os.Args[1:], os.Stdout, os.Stderr)) }
