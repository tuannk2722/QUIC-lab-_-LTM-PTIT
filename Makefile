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
RUNS ?=
WARMUPS ?=
SEED ?=
RESULTS ?=
export PROFILE SCENARIO NETWORK_PROFILE NETEM_SEED RUNS WARMUPS SEED RESULTS

.PHONY: check-go build test test-race certs doctor setup-network server clean-network netem clear-netem inspect-network test-network benchmark benchmark-handshake analyze analysis-deps test-analysis
check-go:
	@test "$$($(GO) version | awk '{print $$3}')" = "go$(GO_VERSION)" || { echo 'Expected Go $(GO_VERSION); see README.md' >&2; exit 3; }

build: check-go
	python3 scripts/build.py "$(GO)" "$(BUILD)"

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

analysis-deps:
	python3 -m pip install --only-binary=:all: --cache-dir .tools/pip-cache --target .tools/analysis -r analysis/requirements.txt

test-analysis:
	python3 -m unittest discover -s analysis -p 'test_*.py' -v
	python3 tests/system/test_bench.py -v
	python3 tests/system/test_audit_p7_p9.py -v
	python3 tests/system/test_handshake.py -v

benchmark: build
	@bench_args=(); \
		if [[ -n $$RUNS ]]; then bench_args+=(--runs="$$RUNS"); fi; \
		if [[ -n $$WARMUPS ]]; then bench_args+=(--warmups="$$WARMUPS"); fi; \
		if [[ -n $$SEED ]]; then bench_args+=(--seed="$$SEED"); fi; \
		if [[ $$NETEM_SEED == none ]]; then bench_args+=(--disable-netem-seed); \
		elif [[ $$NETEM_SEED != default ]]; then echo 'Use SEED for schedule seed or NETEM_SEED=none explicitly.' >&2; exit 2; fi; \
		sudo bash scripts/bench.sh "$${bench_args[@]}"

benchmark-handshake: build
	@bench_args=(--suite=handshake); \
		if [[ -n $$RUNS ]]; then bench_args+=(--runs="$$RUNS"); fi; \
		if [[ -n $$WARMUPS ]]; then bench_args+=(--warmups="$$WARMUPS"); fi; \
		if [[ -n $$SEED ]]; then bench_args+=(--seed="$$SEED"); fi; \
		if [[ $$NETEM_SEED == none ]]; then bench_args+=(--disable-netem-seed); \
		elif [[ $$NETEM_SEED != default ]]; then echo 'Use SEED or explicit NETEM_SEED=none.' >&2; exit 2; fi; \
		sudo bash scripts/bench.sh "$${bench_args[@]}"

analyze:
	@test -n "$$RESULTS" || { echo 'Use make analyze RESULTS=results/<experiment>' >&2; exit 2; }
	python3 analysis/validate.py "$$RESULTS"
	python3 analysis/summarize.py "$$RESULTS"
	python3 analysis/plot.py "$$RESULTS"
