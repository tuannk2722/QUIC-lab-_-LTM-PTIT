package main

import (
	"os"
	"quic-performance-lab/internal/cli"
)

func main() { os.Exit(cli.Run("server", os.Args[1:], os.Stdout, os.Stderr)) }
