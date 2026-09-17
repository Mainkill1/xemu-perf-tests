#!/usr/bin/env python3
"""Compare the exact main → #85 → #87 → #89 161-record XISO results."""

import argparse
import csv
import json
import statistics
from pathlib import Path


ROLES = ("main", "pr85", "pr87", "pr89")
PAIRS = (("main", "pr85"), ("pr85", "pr87"),
         ("pr87", "pr89"), ("main", "pr89"))


def load(path):
    rows = json.loads(path.read_text())
    by_id = {row["id"]: row for row in rows}
    if len(rows) != 161 or len(by_id) != 161:
        raise ValueError(f"{path}: expected 161 unique records")
    return by_id


def compare(reference, candidate):
    if reference["outcome"] != candidate["outcome"]:
        status = "OUTCOME_CHANGED"
    elif not candidate.get("metadata", {}).get(
            "framebuffer_comparison_eligible", True):
        status = "HASH_INELIGIBLE_OUTCOME_MATCH"
    elif reference.get("framebuffer_fnv1a64") != candidate.get(
            "framebuffer_fnv1a64"):
        status = "HASH_CHANGED"
    else:
        status = "OUTCOME_AND_HASH_MATCH"

    ref_us = reference.get("median_us")
    cand_us = candidate.get("median_us")
    timed = (reference["kind"] == candidate["kind"] == "leaf"
             and reference["outcome"] == candidate["outcome"] == "PASS"
             and reference.get("direction") == candidate.get("direction")
             == "lower_is_better" and ref_us and cand_us)
    improvement = (100 * (ref_us - cand_us) / ref_us if timed else None)
    return status, improvement


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    args = parser.parse_args()
    output_rows = []
    summary = {}
    for renderer in ("vulkan", "opengl"):
        data = {
            role: load(args.results / (
                f"{renderer}-main-normalized.json" if role == "main"
                else f"{renderer}-reconciled-{role}-normalized.json"))
            for role in ROLES
        }
        catalog = set(data["main"])
        if any(set(rows) != catalog for rows in data.values()):
            raise ValueError(f"{renderer}: catalog IDs differ")

        renderer_summary = {"record_count": len(catalog),
                            "passes": {role: sum(row["outcome"] == "PASS"
                                                  for row in data[role].values())
                                       for role in ROLES}, "pairs": {}}
        pair_data = {f"{left}_to_{right}": {"unexpected_ids": [],
                                          "timed_improvements": []}
                     for left, right in PAIRS}
        for test_id in sorted(catalog):
            row = {"renderer": renderer, "test_id": test_id,
                   "kind": data["main"][test_id]["kind"]}
            for role in ROLES:
                item = data[role][test_id]
                row[f"{role}_outcome"] = item["outcome"]
                row[f"{role}_hash"] = item.get("framebuffer_fnv1a64") or ""
                row[f"{role}_median_us"] = item.get("median_us") or ""
            for left, right in PAIRS:
                name = f"{left}_to_{right}"
                status, improvement = compare(data[left][test_id],
                                              data[right][test_id])
                row[f"{name}_status"] = status
                row[f"{name}_improvement_pct"] = (
                    f"{improvement:+.2f}" if improvement is not None else "")
                if status in ("OUTCOME_CHANGED", "HASH_CHANGED"):
                    pair_data[name]["unexpected_ids"].append(test_id)
                if improvement is not None:
                    pair_data[name]["timed_improvements"].append(improvement)
            output_rows.append(row)
        for name, values in pair_data.items():
            improvements = values["timed_improvements"]
            renderer_summary["pairs"][name] = {
                "unexpected_ids": values["unexpected_ids"],
                "timed_leaf_count": len(improvements),
                "median_timed_leaf_improvement_pct": (
                    statistics.median(improvements) if improvements else None),
            }
        summary[renderer] = renderer_summary

    with (args.results / "reconciled-comparison.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output_rows[0]))
        writer.writeheader()
        writer.writerows(output_rows)
    (args.results / "reconciled-comparison-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
