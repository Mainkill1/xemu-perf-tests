#!/usr/bin/env python3
"""Compare all records in the PR #89 162-record parent/candidate XISO."""

import argparse
import csv
import json
import statistics
from pathlib import Path


def load(path):
    records = json.loads(path.read_text())
    by_id = {record["id"]: record for record in records}
    if len(records) != 162 or len(by_id) != 162:
        raise ValueError(f"{path}: expected 162 unique records")
    return by_id


def compare(parent, candidate):
    if parent["outcome"] != candidate["outcome"]:
        status = "OUTCOME_CHANGED"
    elif not candidate.get("metadata", {}).get(
            "framebuffer_comparison_eligible", True):
        status = "HASH_INELIGIBLE_OUTCOME_MATCH"
    elif parent.get("framebuffer_fnv1a64") != candidate.get(
            "framebuffer_fnv1a64"):
        status = "HASH_CHANGED"
    else:
        status = "OUTCOME_AND_HASH_MATCH"

    parent_us = parent.get("median_us")
    candidate_us = candidate.get("median_us")
    comparable_time = (parent["kind"] == candidate["kind"] == "leaf"
                       and parent["outcome"] == candidate["outcome"] == "PASS"
                       and parent.get("direction") == candidate.get("direction")
                       == "lower_is_better" and parent_us and candidate_us)
    improvement = (100 * (parent_us - candidate_us) / parent_us
                   if comparable_time else None)
    return status, improvement


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--output-prefix", required=True, type=Path)
    args = parser.parse_args()

    parent = load(args.parent)
    candidate = load(args.candidate)
    if parent.keys() != candidate.keys():
        raise ValueError("parent and candidate test IDs differ")

    rows = []
    timed = []
    unexpected = []
    for test_id in sorted(parent):
        a, b = parent[test_id], candidate[test_id]
        status, improvement = compare(a, b)
        if status in ("OUTCOME_CHANGED", "HASH_CHANGED"):
            unexpected.append(test_id)
        if improvement is not None:
            timed.append(improvement)
        rows.append({
            "test_id": test_id,
            "kind": a["kind"],
            "parent_outcome": a["outcome"],
            "candidate_outcome": b["outcome"],
            "parent_hash": a.get("framebuffer_fnv1a64") or "",
            "candidate_hash": b.get("framebuffer_fnv1a64") or "",
            "parent_median_us": a.get("median_us") or "",
            "candidate_median_us": b.get("median_us") or "",
            "status": status,
            "improvement_pct": (f"{improvement:+.2f}"
                                if improvement is not None else ""),
        })

    summary = {
        "record_count": len(rows),
        "parent_passes": sum(r["outcome"] == "PASS" for r in parent.values()),
        "candidate_passes": sum(r["outcome"] == "PASS"
                                for r in candidate.values()),
        "unexpected_ids": unexpected,
        "timed_leaf_count": len(timed),
        "median_timed_leaf_improvement_pct": statistics.median(timed),
        "faster_leaves": sum(value > 0 for value in timed),
        "slower_leaves": sum(value < 0 for value in timed),
        "tied_leaves": sum(value == 0 for value in timed),
    }
    with args.output_prefix.with_suffix(".csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    args.output_prefix.with_suffix(".json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
