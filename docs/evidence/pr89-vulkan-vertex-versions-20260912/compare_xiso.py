#!/usr/bin/env python3
"""Compare an exact-parent XISO CSV with normalized candidate suite records."""

import argparse
import csv
import json
import statistics
from pathlib import Path


HASH_INELIGIBLE = {
    "game_load.s3tc_sync_factor.dxt1_same_address_queued",
    "game_load.s3tc_sync_factor.rgba8_same_address_queued",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-csv", type=Path, required=True)
    parser.add_argument("--vulkan", type=Path, required=True)
    parser.add_argument("--opengl", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    with args.parent_csv.open(newline="") as stream:
        parent_rows = list(csv.DictReader(stream))
    parents = {(row["renderer"], row["test_id"]): row for row in parent_rows}
    if len(parents) != len(parent_rows):
        raise ValueError("duplicate parent test ID")

    rows = []
    timed_values = {"vulkan": [], "opengl": []}
    for renderer, path in (("vulkan", args.vulkan), ("opengl", args.opengl)):
        candidate_rows = json.loads(path.read_text())
        if len(candidate_rows) != 160:
            raise ValueError(f"{renderer}: expected 160 records, got {len(candidate_rows)}")
        seen = set()
        for candidate in candidate_rows:
            test_id = candidate["id"]
            if test_id in seen:
                raise ValueError(f"{renderer}: duplicate {test_id}")
            seen.add(test_id)
            parent = parents[(renderer, test_id)]
            candidate_hash = candidate.get("framebuffer_fnv1a64", "")
            if candidate["outcome"] != parent["outcome"]:
                comparison = "OUTCOME_CHANGED"
            elif test_id in HASH_INELIGIBLE:
                comparison = "HASH_INELIGIBLE_OUTCOME_MATCH"
            elif candidate_hash != parent["framebuffer_fnv1a64"]:
                comparison = "HASH_CHANGED"
            else:
                comparison = "OUTCOME_AND_HASH_MATCH"

            parent_us = int(parent["guest_median_us"] or 0)
            candidate_us = candidate.get("median_us") or 0
            timed = (candidate["kind"] == "leaf"
                     and candidate["outcome"] == parent["outcome"] == "PASS"
                     and candidate.get("direction") == "lower_is_better"
                     and parent_us > 0 and candidate_us > 0)
            improvement = 100 * (1 - candidate_us / parent_us) if timed else None
            if improvement is not None:
                timed_values[renderer].append(improvement)
            rows.append({
                "renderer": renderer,
                "test_id": test_id,
                "kind": candidate["kind"],
                "parent_outcome": parent["outcome"],
                "candidate_outcome": candidate["outcome"],
                "parent_framebuffer_fnv1a64": parent["framebuffer_fnv1a64"],
                "candidate_framebuffer_fnv1a64": candidate_hash,
                "comparison": comparison,
                "raw_direction": "+bad" if timed else "",
                "parent_median_us": parent_us or "",
                "candidate_median_us": candidate_us or "",
                "improvement_pct": f"{improvement:+.2f}" if timed else "",
            })
        if len(seen) != 160:
            raise ValueError(f"{renderer}: incomplete test set")
    if len(rows) != len(parents):
        raise ValueError("parent and candidate catalogs differ")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    for renderer in ("vulkan", "opengl"):
        subset = [row for row in rows if row["renderer"] == renderer]
        unexpected = [row["test_id"] for row in subset
                      if row["comparison"] in ("OUTCOME_CHANGED", "HASH_CHANGED")]
        timed = timed_values[renderer]
        print(json.dumps({
            "renderer": renderer,
            "records": len(subset),
            "unexpected": unexpected,
            "timed_leaves": len(timed),
            "faster": sum(value > 0 for value in timed),
            "slower": sum(value < 0 for value in timed),
            "median_improvement_pct": statistics.median(timed),
        }))


if __name__ == "__main__":
    main()
