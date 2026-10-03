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
CAPTURE_NS ?= qclient
CAPTURE_SECONDS ?= 30
CAPTURE_OUT ?=
DEMO_OUT ?=
DEMO_BACKUP ?=
export PROFILE SCENARIO NETWORK_PROFILE NETEM_SEED RUNS WARMUPS SEED RESULTS CAPTURE_NS CAPTURE_SECONDS CAPTURE_OUT DEMO_OUT DEMO_BACKUP

.PHONY: check-go build test test-race certs doctor setup-network server clean-network netem clear-netem inspect-network test-network benchmark benchmark-handshake analyze analysis-deps test-analysis
check-go:
	@test "$$($(GO) version | awk '{print $$3}')" = "go$(GO_VERSION)" || { echo 'Expected Go $(GO_VERSION); see README.md' >&2; exit 3; }

build: check-go
	python3 scripts/build.py "$(GO)" "$(BUILD)"

tls-keylog-overlay: check-go
	python3 scripts/tls_keylog_overlay.py "$(GO)"

test: tls-keylog-overlay
	$(GO) test -overlay="$(CURDIR)/.tools/tls-keylog-overlay/overlay.json" -mod=readonly ./...

test-race: tls-keylog-overlay
	$(GO) test -overlay="$(CURDIR)/.tools/tls-keylog-overlay/overlay.json" -mod=readonly -race ./...

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
	python3 tests/system/test_g11_lifecycle.py -v

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

.PHONY: capture decoder-deps gate-g11 tls-keylog-overlay
capture:
	@capture_out="$$CAPTURE_OUT"; \
		if [[ -z $$capture_out ]]; then capture_out="$(CURDIR)/results/capture-$$(date -u +%Y%m%dT%H%M%S)-$$RANDOM"; fi; \
		sudo bash scripts/capture.sh "$$CAPTURE_NS" "$$capture_out" "$$CAPTURE_SECONDS"

decoder-deps:
	python3 scripts/prepare-decoder.py

gate-g11: build
	sudo bash tests/system/run.sh --gate G11

.PHONY: demo-quic-basic demo-baseline demo-loss demo-0rtt cleanup gate-g12 test-demo
# Live commands use prepared binaries/dependencies; no build or download here.
demo-quic-basic demo-baseline demo-loss demo-0rtt:
	@demo_kind="$@"; demo_kind="$${demo_kind#demo-}"; \
		[[ $$demo_kind != quic-basic ]] || demo_kind=basic; \
		demo_args=("$$demo_kind"); \
		[[ -z $$DEMO_OUT ]] || demo_args+=(--out="$$DEMO_OUT"); \
		[[ -z $$DEMO_BACKUP ]] || demo_args+=(--backup="$$DEMO_BACKUP"); \
		sudo env NETEM_SEED="$$NETEM_SEED" bash scripts/demo.sh "$${demo_args[@]}"

cleanup: clean-network

test-demo:
	python3 tests/system/test_demo.py -v

gate-g12:
	bash scripts/run-g12-review.sh
