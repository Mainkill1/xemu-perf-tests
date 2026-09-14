#!/usr/bin/env python3
"""Export compact, source-pinned per-test XISO metrics from a PR71 campaign."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("summaries", type=Path,
                        help="directory of <campaign-cell-label>.json summaries")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    if receipt["status"] != "passed":
        raise SystemExit("campaign is not complete")
    cells = [cell for cell in receipt["cells"] if cell.get("record_count")]
    if len(cells) < 9:
        raise SystemExit("missing full-suite comparison cells")

    summaries: dict[str, dict] = {}
    records_by_cell: dict[str, dict[str, dict]] = {}
    rows: list[dict] = []
    inputs = {"campaign.json": sha256(args.receipt)}
    for cell in cells:
        label = cell["label"]
        path = args.summaries / f"{label}.json"
        summary = json.loads(path.read_text(encoding="utf-8"))
        inputs[f"{label}.json"] = sha256(path)
        if (summary["build"]["SOURCE_SHA"] != cell["source_commit"] or
                summary["build"]["XEMU_SHA256"] != cell["xemu_sha256"] or
                len(summary["records"]) != cell["record_count"]):
            raise SystemExit(f"{label}: identity or record-count mismatch")
        summaries[label] = summary
        records_by_cell[label] = {row["id"]: row for row in summary["records"]}
        for record in summary["records"]:
            rows.append({
                "cell": label,
                "role": cell["role"],
                "renderer": cell["renderer"],
                "hybrid": cell["hybrid_ubershaders"],
                "fastpath": cell.get("shader_fastpath", "off"),
                "cache_phase": cell["cache_phase"],
                "source_commit": cell["source_commit"],
                "xemu_sha256": cell["xemu_sha256"],
                "test_id": record["id"],
                "kind": record["kind"],
                "outcome": record["outcome"],
                "sample_count": record.get("sample_count"),
                "iterations": record.get("iterations"),
                "guest_average_us": record.get("guest_average_us"),
                "guest_median_us": record.get("guest_median_us"),
                "guest_mad_us": record.get("guest_mad_us"),
                "completion_wait_us": record.get("completion_wait_us"),
                "framebuffer_fnv1a64": record.get("framebuffer_fnv1a64"),
            })

    baseline = {
        cell["renderer"]: cell["label"] for cell in cells
        if cell["role"] == "fixed_baseline"
    }
    previous = {
        cell["renderer"]: cell["label"] for cell in cells
        if cell["role"] == "previous_main"
    }
    comparisons: list[dict] = []
    for cell in cells:
        if cell["role"] != "candidate":
            continue
        label = cell["label"]
        renderer = cell["renderer"]
        references = [("baseline", baseline.get(renderer)),
                      ("previous_main", previous.get(renderer))]
        if cell["hybrid_ubershaders"] == "on":
            control = next((other["label"] for other in cells
                            if other["role"] == "candidate" and
                            other["renderer"] == renderer and
                            other["cache_phase"] == cell["cache_phase"] and
                            other["hybrid_ubershaders"] == "off" and
                            other.get("shader_fastpath", "off") == "off"), None)
            references.append(("same_candidate_hybrid_off", control))
        if cell.get("shader_fastpath") == "on":
            control = next((other["label"] for other in cells
                            if other["role"] == "candidate" and
                            other["renderer"] == renderer and
                            other["hybrid_ubershaders"] == cell["hybrid_ubershaders"] and
                            other["cache_phase"] == cell["cache_phase"] and
                            other.get("shader_fastpath", "off") == "off"), None)
            references.append(("same_hybrid_fastpath_off", control))
        for reference_kind, reference_label in references:
            if not reference_label:
                raise SystemExit(f"{label}: missing {reference_kind} reference")
            reference_records = records_by_cell[reference_label]
            for test_id, candidate in records_by_cell[label].items():
                reference = reference_records.get(test_id)
                reference_median = reference.get("guest_median_us") if reference else None
                candidate_median = candidate.get("guest_median_us")
                comparable = (reference is not None and
                              reference["outcome"] == candidate["outcome"] == "PASS" and
                              isinstance(reference_median, (int, float)) and
                              isinstance(candidate_median, (int, float)) and
                              reference_median > 0 and candidate_median > 0)
                improvement = (100 * (reference_median - candidate_median) /
                               reference_median) if comparable else None
                comparisons.append({
                    "candidate_cell": label,
                    "reference_kind": reference_kind,
                    "reference_cell": reference_label,
                    "test_id": test_id,
                    "candidate_outcome": candidate["outcome"],
                    "reference_outcome": reference["outcome"] if reference else "ABSENT",
                    "candidate_median_us": candidate_median,
                    "reference_median_us": reference_median,
                    "improvement_pct": f"{improvement:+.3f}" if comparable else "",
                })

    args.output.mkdir(parents=True, exist_ok=True)
    per_test_path = args.output / "per-test.csv"
    comparisons_path = args.output / "per-test-improvement.csv"
    gated_path = args.output / "fixed-baseline-gated-controls.csv"
    write_csv(per_test_path, list(rows[0]), rows)
    write_csv(comparisons_path, list(comparisons[0]), comparisons)
    gated_rows = [{
        "cell": cell["label"],
        "test_id": cell["test_id"],
        "renderer": cell["renderer"],
        "outcome": cell["outcome"],
        "classification": cell["classification"],
        "source_commit": cell["source_commit"],
        "xemu_sha256": cell["xemu_sha256"],
    } for cell in receipt["cells"]
        if cell.get("workload") == "full_xiso_gated_leaf"]
    if gated_rows:
        write_csv(gated_path, list(gated_rows[0]), gated_rows)

    lines = ["# PR #71 XISO per-test comparison", "",
             "Positive improvement means a shorter guest test median. Each test",
             "has its own workload; the median across tests is descriptive, not an",
             "overall gameplay speedup. Only matching PASS outcomes with measured",
             "positive medians are compared. Full rows and framebuffer hashes are",
             "in `per-test.csv`; individual improvements are in",
             "`per-test-improvement.csv`. Isolated inherited baseline records",
             "are in `fixed-baseline-gated-controls.csv`.", "",
             "| Candidate | Reference | Comparable tests | Better | Worse | Median improvement |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for candidate_label, reference_kind in sorted({
            (row["candidate_cell"], row["reference_kind"]) for row in comparisons}):
        group = [float(row["improvement_pct"]) for row in comparisons
                 if row["candidate_cell"] == candidate_label and
                 row["reference_kind"] == reference_kind and row["improvement_pct"]]
        lines.append(f"| {candidate_label} | {reference_kind} | {len(group)} | "
                     f"{sum(value > 0 for value in group)} | "
                     f"{sum(value < 0 for value in group)} | "
                     f"{statistics.median(group):+.3f}% |")
    (args.output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    manifest = {
        "campaign_id": receipt["campaign_id"],
        "xiso": receipt["maintained_xiso"],
        "full_suite_cells": len(cells),
        "per_test_rows": len(rows),
        "comparison_rows": len(comparisons),
        "fixed_baseline_gated_rows": len(gated_rows),
        "input_sha256": inputs,
        "output_sha256": {
            per_test_path.name: sha256(per_test_path),
            comparisons_path.name: sha256(comparisons_path),
            **({gated_path.name: sha256(gated_path)} if gated_rows else {}),
        },
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{len(cells)} cells, {len(rows)} per-test rows, "
          f"{len(comparisons)} comparisons")


if __name__ == "__main__":
    main()
