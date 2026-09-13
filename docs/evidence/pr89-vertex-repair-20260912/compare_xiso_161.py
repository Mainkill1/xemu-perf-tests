#!/usr/bin/env python3
"""Compare PR89 and its exact parent with the same 161-record XISO image."""

import argparse
import csv
import json
import statistics
from pathlib import Path


def load(path):
    rows = json.loads(path.read_text())
    by_id = {row["id"]: row for row in rows}
    if len(rows) != 161 or len(by_id) != 161:
        raise ValueError(f"{path}: expected 161 unique records, found {len(rows)}")
    return by_id


def compare(reference, candidate):
    if reference["outcome"] != candidate["outcome"]:
        status = "OUTCOME_CHANGED"
    elif not candidate.get("metadata", {}).get("framebuffer_comparison_eligible", True):
        status = "HASH_INELIGIBLE_OUTCOME_MATCH"
    elif reference.get("framebuffer_fnv1a64") != candidate.get("framebuffer_fnv1a64"):
        status = "HASH_CHANGED"
    else:
        status = "OUTCOME_AND_HASH_MATCH"

    reference_us = reference.get("median_us")
    candidate_us = candidate.get("median_us")
    comparable_time = (
        reference["kind"] == candidate["kind"] == "leaf"
        and reference["outcome"] == candidate["outcome"] == "PASS"
        and reference.get("direction") == candidate.get("direction")
        == "lower_is_better"
        and reference_us and candidate_us
    )
    improvement = (100 * (reference_us - candidate_us) / reference_us
                   if comparable_time else None)
    return status, improvement


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    summary = {}
    for renderer in ("vulkan", "opengl"):
        inputs = {role: load(args.results / f"{renderer}-{role}-normalized.json")
                  for role in ("parent", "candidate")}
        baseline_path = args.results / f"{renderer}-baseline-normalized.json"
        if baseline_path.exists():
            inputs["baseline"] = load(baseline_path)
        pr85_path = args.results / f"{renderer}-pr85-normalized.json"
        if pr85_path.exists():
            inputs["pr85"] = load(pr85_path)
        if len({frozenset(x) for x in inputs.values()}) != 1:
            raise ValueError(f"{renderer}: catalog IDs differ")
        timed = {role: [] for role in ("parent", "baseline", "pr85_parent")}
        unexpected = {role: [] for role in timed}
        for test_id in sorted(inputs["candidate"]):
            candidate = inputs["candidate"][test_id]
            baseline = inputs.get("baseline", {}).get(test_id)
            pr85 = inputs.get("pr85", {}).get(test_id)
            parent = inputs["parent"][test_id]
            statuses = {}
            improvements = {}
            for role, reference in (("parent", parent), ("baseline", baseline)):
                if reference is None:
                    statuses[role], improvements[role] = "NOT_COMPARABLE", None
                    continue
                statuses[role], improvements[role] = compare(reference, candidate)
                if statuses[role] in ("OUTCOME_CHANGED", "HASH_CHANGED"):
                    unexpected[role].append(test_id)
                if improvements[role] is not None:
                    timed[role].append(improvements[role])
            if pr85 is None:
                pr85_parent_status, pr85_parent_improvement = "NOT_COMPARABLE", None
            else:
                pr85_parent_status, pr85_parent_improvement = compare(pr85, parent)
                if pr85_parent_status in ("OUTCOME_CHANGED", "HASH_CHANGED"):
                    unexpected["pr85_parent"].append(test_id)
                if pr85_parent_improvement is not None:
                    timed["pr85_parent"].append(pr85_parent_improvement)
            rows.append({
                "renderer": renderer,
                "test_id": test_id,
                "kind": candidate["kind"],
                "baseline_outcome": baseline["outcome"] if baseline else "",
                "pr85_outcome": pr85["outcome"] if pr85 else "",
                "parent_outcome": parent["outcome"],
                "candidate_outcome": candidate["outcome"],
                "candidate_vs_baseline": statuses["baseline"],
                "parent_vs_pr85": pr85_parent_status,
                "candidate_vs_parent": statuses["parent"],
                "raw_direction": "+bad" if improvements["parent"] is not None else "",
                "baseline_median_us": baseline.get("median_us") or "" if baseline else "",
                "pr85_median_us": pr85.get("median_us") or "" if pr85 else "",
                "parent_median_us": parent.get("median_us") or "",
                "candidate_median_us": candidate.get("median_us") or "",
                "improvement_parent_vs_pr85_pct": (
                    f"{pr85_parent_improvement:+.2f}"
                    if pr85_parent_improvement is not None else ""),
                "improvement_vs_baseline_pct": (
                    f"{improvements['baseline']:+.2f}"
                    if improvements["baseline"] is not None else ""),
                "improvement_vs_parent_pct": (
                    f"{improvements['parent']:+.2f}"
                    if improvements["parent"] is not None else ""),
                "baseline_hash": baseline.get("framebuffer_fnv1a64") or "" if baseline else "",
                "pr85_hash": pr85.get("framebuffer_fnv1a64") or "" if pr85 else "",
                "parent_hash": parent.get("framebuffer_fnv1a64") or "",
                "candidate_hash": candidate.get("framebuffer_fnv1a64") or "",
            })
        summary[renderer] = {
            "records": 161,
            "candidate_vs_parent_unexpected": unexpected["parent"],
            "candidate_vs_baseline_unexpected": unexpected["baseline"] if baseline_path.exists() else None,
            "parent_vs_pr85_unexpected": unexpected["pr85_parent"] if pr85_path.exists() else None,
            "timed_parent_leaves": len(timed["parent"]),
            "median_improvement_vs_parent_pct": statistics.median(timed["parent"]),
            "timed_pr85_parent_leaves": len(timed["pr85_parent"]),
            "median_improvement_parent_vs_pr85_pct": (
                statistics.median(timed["pr85_parent"]) if pr85_path.exists() else None),
            "timed_baseline_leaves": len(timed["baseline"]) if baseline_path.exists() else 0,
            "median_improvement_vs_baseline_pct": (
                statistics.median(timed["baseline"]) if baseline_path.exists() else None),
        }
    if len(rows) != 322:
        raise ValueError("incomplete result set")
    with (args.results / "comparison.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (args.results / "comparison-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
