SHELL := /bin/bash
GO_VERSION := 1.27.1
GO := $(if $(wildcard .tools/go$(GO_VERSION)/bin/go),$(CURDIR)/.tools/go$(GO_VERSION)/bin/go,go)
export GOTOOLCHAIN := local
export GOPATH := $(CURDIR)/.tools/gopath
export GOCACHE := $(CURDIR)/.tools/gocache
export GOMAXPROCS := 2
export GOFLAGS := -p=2
export PATH := $(dir $(GO)):$(PATH)
BUILD := $(shell git rev-parse --short HEAD 2>/dev/null || echo uncommitted)
CERT_DIR ?= certs
CERT_FORCE ?=
REPORT ?= results/doctor.txt
PROFILE ?= bulk
SCENARIO ?= rtt50-loss0
NETWORK_PROFILE ?= ingress-ifb
NETEM_SEED ?= default
export PROFILE SCENARIO NETWORK_PROFILE NETEM_SEED

.PHONY: check-go build test test-race certs doctor setup-network server clean-network netem clear-netem inspect-network test-network
check-go:
	@test "$$($(GO) version | awk '{print $$3}')" = "go$(GO_VERSION)" || { echo 'Expected Go $(GO_VERSION); see README.md' >&2; exit 3; }

build: check-go
	@mkdir -p bin
	$(GO) build -mod=readonly -trimpath -ldflags '-X quic-performance-lab/internal/cli.Build=$(BUILD)' -o bin/server ./cmd/server
	$(GO) build -mod=readonly -trimpath -ldflags '-X quic-performance-lab/internal/cli.Build=$(BUILD)' -o bin/client ./cmd/client
	$(GO) build -mod=readonly -trimpath -ldflags '-X quic-performance-lab/internal/cli.Build=$(BUILD)' -o bin/bench ./cmd/bench

test: check-go
	$(GO) test -mod=readonly ./...

test-race: check-go
	$(GO) test -mod=readonly -race ./...

certs:
	bash scripts/gen-cert.sh --dir "$(CERT_DIR)" $(CERT_FORCE)

doctor:
	bash scripts/doctor.sh "$(REPORT)"

setup-network:
	sudo bash scripts/network/setup.sh

server: build
	@server_bin=$$(realpath -e -- ./bin/server) || exit 1; \
		sudo bash scripts/run-in-netns.sh qserver -- "$$server_bin" \
		--transport=both --listen=0.0.0.0:4433 --profile="$$PROFILE"

clean-network:
	sudo bash scripts/network/teardown.sh

netem:
	sudo bash scripts/network/netem.sh --scenario="$$SCENARIO" --profile="$$NETWORK_PROFILE" --seed="$$NETEM_SEED"

clear-netem:
	sudo bash scripts/network/clear-netem.sh

inspect-network:
	sudo bash scripts/network/inspect.sh

test-network:
	python3 tests/system/test_network.py
