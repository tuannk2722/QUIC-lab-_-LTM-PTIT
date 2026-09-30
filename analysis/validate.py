#!/usr/bin/env python3
"""Validate schema v1 raw JSON and CSV trial records without extra packages."""

import argparse
import csv
import json
import math
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/result-records.schema.json"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def equal(a, b, name, tolerance=1e-6):
    require(a is not None and b is not None and math.isclose(a, b, rel_tol=1e-6, abs_tol=tolerance),
            f"{name}: {a} != {b}")


def read_csv(path, definition):
    columns = definition["x-csv-columns"]
    properties = definition["properties"]
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        require(reader.fieldnames == columns, f"{path}: incorrect header")
        rows = []
        for index, raw in enumerate(reader, start=2):
            require(None not in raw, f"{path}:{index}: extra columns")
            row = {}
            for key in columns:
                value = raw[key]
                rule = properties[key]
                types = rule["type"] if isinstance(rule["type"], list) else [rule["type"]]
                if value == "" and "null" in types:
                    parsed = None
                elif "integer" in types:
                    require(value is not None and value.isdecimal(), f"{path}:{index}:{key}: invalid integer")
                    parsed = int(value)
                elif "number" in types:
                    try:
                        parsed = float(value)
                    except (ValueError, TypeError):
                        raise ValueError(f"{path}:{index}:{key}: invalid number") from None
                    require(math.isfinite(parsed), f"{path}:{index}:{key}: nonfinite")
                elif "boolean" in types:
                    require(value in ("true", "false"), f"{path}:{index}:{key}: invalid boolean")
                    parsed = value == "true"
                else:
                    parsed = value
                if parsed is None:
                    require("null" in types, f"{path}:{index}:{key}: null not allowed")
                else:
                    if "const" in rule:
                        require(parsed == rule["const"], f"{path}:{index}:{key}: wrong version")
                    if "enum" in rule:
                        require(parsed in rule["enum"], f"{path}:{index}:{key}: invalid enum")
                    if "minimum" in rule:
                        require(parsed >= rule["minimum"], f"{path}:{index}:{key}: below minimum")
                    if "maximum" in rule:
                        require(parsed <= rule["maximum"], f"{path}:{index}:{key}: above maximum")
                    if rule.get("format") == "date-time":
                        require(datetime.fromisoformat(parsed.replace("Z", "+00:00")).tzinfo is not None,
                                f"{path}:{index}:{key}: invalid timestamp")
                row[key] = parsed
            rows.append(row)
    return rows


def validate(directory):
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))["$defs"]
    runs = read_csv(directory / "runs.csv", schema["run"])
    streams = read_csv(directory / "streams.csv", schema["stream"])
    require(runs, "no runs")
    run_ids = [row["run_id"] for row in runs]
    require(len(set(run_ids)) == len(run_ids), "duplicate run_id")
    by_run = {}
    for row in streams:
        by_run.setdefault(row["run_id"], []).append(row)
    require(set(by_run) == set(run_ids), "streams foreign key or missing rows")
    for run in runs:
        rid = run["run_id"]
        group = by_run[rid]
        require(len(group) == run["resource_count"], f"{rid}: wrong stream count")
        require({s["resource_id"] for s in group} == set(range(1, run["resource_count"] + 1)), f"{rid}: duplicate/missing resource")
        require(all(s["experiment_id"] == run["experiment_id"] for s in group), f"{rid}: experiment FK")
        require(run["bytes_expected"] == sum(s["bytes_expected"] for s in group), f"{rid}: expected bytes")
        require(run["bytes_received"] == sum(s["bytes_received"] for s in group), f"{rid}: received bytes")
        require(all(s["bytes_received"] <= s["bytes_expected"] for s in group), f"{rid}: byte overflow")
        if run["transport"] == "tcp":
            require(all(s["transport_stream_id"] is None for s in group), f"{rid}: TCP native stream ID")
            if run["tcp_connect_ms"] is not None and run["handshake_ms"] is not None:
                equal(run["tls_handshake_ms"], run["handshake_ms"] - run["tcp_connect_ms"], f"{rid}: TLS handshake")
        else:
            require(run["tcp_connect_ms"] is None and run["tls_handshake_ms"] is None, f"{rid}: QUIC TCP metric")
            ids = [s["transport_stream_id"] for s in group if s["transport_stream_id"] is not None]
            require(len(ids) == len(set(ids)), f"{rid}: duplicate QUIC stream ID")
        if run["handshake_ms"] is not None:
            equal(run["connect_ms"], run["handshake_ms"], f"{rid}: connect alias")
        for s in group:
            if s["first_byte_ms"] is not None:
                equal(s["ttfb_request_ms"], s["first_byte_ms"] - s["request_start_ms"], f"{rid}/{s['resource_id']}: TTFB")
            if s["complete_ms"] is not None:
                equal(s["completion_request_ms"], s["complete_ms"] - s["request_start_ms"], f"{rid}/{s['resource_id']}: completion")
        first = [s["first_byte_ms"] for s in group if s["first_byte_ms"] is not None]
        if first:
            equal(run["ttfa_ms"], min(first), f"{rid}: TTFA")
        else:
            require(run["ttfa_ms"] is None, f"{rid}: false TTFA")
        if run["success"]:
            require(run["bytes_received"] == run["bytes_expected"] and all(s["success"] and s["checksum_ok"] for s in group), f"{rid}: incomplete success")
            require(run["error_code"] == "" and run["error_message"] == "", f"{rid}: success error fields")
            complete = [s["complete_ms"] for s in group]
            request = [s["request_start_ms"] for s in group]
            require(None not in complete and None not in request, f"{rid}: missing success milestones")
            equal(run["total_ms"], max(complete), f"{rid}: total")
            equal(run["transfer_ms"], max(complete) - min(request), f"{rid}: transfer")
            if run["transfer_ms"] > 0:
                equal(run["goodput_mbps"], 8 * run["bytes_received"] / (run["transfer_ms"] * 1000), f"{rid}: goodput")
            else:
                require(run["goodput_mbps"] is None, f"{rid}: zero-duration goodput")
            if run["total_ms"] > 0:
                equal(run["e2e_goodput_mbps"], 8 * run["bytes_received"] / (run["total_ms"] * 1000), f"{rid}: e2e goodput")
            else:
                require(run["e2e_goodput_mbps"] is None, f"{rid}: zero-duration e2e goodput")
        else:
            require(run["error_code"] != "" and run["total_ms"] is None and run["transfer_ms"] is None and
                    run["goodput_mbps"] is None and run["e2e_goodput_mbps"] is None, f"{rid}: failure metrics")
        require(run["elapsed_ms"] >= 0, f"{rid}: negative elapsed")
        raw = json.loads((directory / "raw" / (rid + ".json")).read_text(encoding="utf-8"))
        require(raw["run"] == run, f"{rid}: raw run disagrees with CSV")
        require(raw["streams"] == sorted(group, key=lambda s: s["resource_id"]), f"{rid}: raw streams disagree with CSV")
    counts = Counter(row["phase"] for row in runs)
    return {"status": "PASS", "attempted": len(runs), "success": sum(r["success"] for r in runs),
            "failed": sum(not r["success"] for r in runs), "measured_trials": counts["measured"],
            "warmup_trials_excluded": counts["warmup"], "evidence_trials_excluded": counts["evidence"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("results_dir", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.results_dir), sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
