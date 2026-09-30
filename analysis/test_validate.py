#!/usr/bin/env python3
"""Contract checks over copies of actual G06 trials; never edits raw evidence."""

import argparse
import csv
import json
import shutil
import tempfile
from pathlib import Path

from validate import validate


def rows(path):
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.reader(source))


def put(path, data):
    with path.open("w", newline="", encoding="utf-8") as target:
        csv.writer(target).writerows(data)


def rejected(directory, label):
    try:
        validate(directory)
    except ValueError:
        return
    raise AssertionError(f"validator accepted {label}")


def test(source):
    with tempfile.TemporaryDirectory(prefix="g06-validator-") as tmp:
        dest = Path(tmp)
        (dest / "raw").mkdir()
        for name in ("runs", "streams"):
            merged = None
            for trial in ("tcp_success", "quic_success", "tcp_failure"):
                part = rows(source / trial / f"{name}.csv")
                if merged is None:
                    merged = part
                else:
                    assert part[0] == merged[0]
                    merged.extend(part[1:])
            put(dest / f"{name}.csv", merged)
        for trial in ("tcp_success", "quic_success", "tcp_failure"):
            for raw in (source / trial / "raw").glob("*.json"):
                shutil.copy2(raw, dest / "raw" / raw.name)
        counts = validate(dest)
        assert counts["attempted"] == 3 and counts["success"] == 2 and counts["failed"] == 1, counts
        runs = rows(dest / "runs.csv")
        phase = runs[0].index("phase")
        runs[1][phase] = "warmup"
        put(dest / "runs.csv", runs)
        raw_path = dest / "raw" / "tcp_success.json"
        raw = json.loads(raw_path.read_text())
        raw["run"]["phase"] = "warmup"
        raw_path.write_text(json.dumps(raw), encoding="utf-8")
        counts = validate(dest)
        assert counts["measured_trials"] == 2 and counts["warmup_trials_excluded"] == 1, counts
        runs.append(list(runs[1]))
        put(dest / "runs.csv", runs)
        rejected(dest, "duplicate run ID")
        runs.pop()
        put(dest / "runs.csv", runs)
        streams = rows(dest / "streams.csv")
        streams.pop()
        put(dest / "streams.csv", streams)
        rejected(dest, "missing resource row")
    print("G06 validator: 3 actual trials, failure retained, warmup excluded, duplicate ID and missing stream rejected")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("actual_g06_parent", type=Path)
    test(parser.parse_args().actual_g06_parent)
