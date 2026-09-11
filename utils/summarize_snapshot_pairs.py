"""Compare completed snapshot pairs without pooling per-run percentiles.

Input is a JSON list of run rows (see the accompanying tests and PR59 evidence).
This tool computes descriptive comparisons, never a performance acceptance PASS.
"""

import argparse
import json
import math
import statistics
from pathlib import Path


METRICS = {
    "cadence_hz": "+good",
    "mean_ms": "+bad",
    "p95_ms": "+bad",
    "p99_ms": "+bad",
    "maximum_ms": "+bad",
}


def compare_pairs(rows, expected_pairs, expected_renderers=None):
    if not isinstance(expected_pairs, int) or expected_pairs < 1:
        raise ValueError("expected pairs must be a positive integer")
    groups, identities, seen = {}, {}, set()
    duration = None
    for row in rows:
        if row["phase"] == "pilot":
            continue
        if row["phase"] != "measured" or row["status"] != "VALID":
            raise ValueError(f"invalid measured run: {row['run_id']}")
        role = row["build"]
        if role not in ("B", "AM"):
            raise ValueError(f"unknown build role: {role}")
        if row["run_id"] in seen:
            raise ValueError(f"duplicate run id: {row['run_id']}")
        seen.add(row["run_id"])
        identity = (row["source_commit"], row["exe_sha256"])
        if not all(identity) or identities.setdefault(role, identity) != identity:
            raise ValueError(f"build identity drift for {role}")
        seconds = row["duration_seconds"]
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("invalid measured duration")
        duration = seconds if duration is None else duration
        if seconds != duration:
            raise ValueError("measurement duration drift")
        for metric in METRICS:
            value = row["metrics"][metric]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"invalid {metric}: {value}")
        pairs = groups.setdefault(row["renderer"], {})
        pair = pairs.setdefault(row["pair"], {})
        if role in pair:
            raise ValueError(f"duplicate role in pair {row['pair']}")
        pair[role] = row
    if not groups:
        raise ValueError("no measured pairs")
    if expected_renderers is not None and set(groups) != set(expected_renderers):
        raise ValueError("missing or unexpected renderer")
    result = {}
    for renderer, pairs in sorted(groups.items()):
        if set(pairs) != set(range(1, expected_pairs + 1)):
            raise ValueError(f"incomplete declared pairs for {renderer}")
        output = []
        for pair_id, pair in sorted(pairs.items()):
            if set(pair) != {"B", "AM"}:
                raise ValueError(f"incomplete pairs: {renderer}/{pair_id}")
            improvements = {}
            for metric, direction in METRICS.items():
                reference = pair["B"]["metrics"][metric]
                candidate = pair["AM"]["metrics"][metric]
                change = 100 * (candidate / reference - 1)
                improvements[metric] = change if direction == "+good" else -change
            output.append({"pair": pair_id, "reference_run": pair["B"]["run_id"],
                           "candidate_run": pair["AM"]["run_id"],
                           "improvement_percent": improvements})
        summary = {}
        for metric, direction in METRICS.items():
            values = [pair["improvement_percent"][metric] for pair in output]
            summary[metric] = {
                "raw_direction": direction,
                "median_improvement_percent": statistics.median(values),
                "minimum_improvement_percent": min(values),
                "maximum_improvement_percent": max(values),
                "pairs_below_minus_two_percent": sum(value < -2 for value in values),
            }
        result[renderer] = {"pairs": output, "summary": summary,
                            "qualification": "descriptive only; not an acceptance decision"}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", type=Path)
    parser.add_argument("--expected-pairs", type=int, required=True)
    parser.add_argument("--renderer", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.runs.read_text(encoding="utf-8"))
    result = compare_pairs(rows, args.expected_pairs, args.renderer)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
