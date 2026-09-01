#!/usr/bin/env python3
"""Compare deterministic per-record hashes from xemu-perf run files."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


HASH_FIELDS = (
    ("framebuffer", "framebuffer_fnv1a64"),
    ("work", "work_checksum"),
    ("result", "result_checksum"),
)


class InputError(ValueError):
    """A run file cannot be compared safely."""


def _load_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    if isinstance(metadata, str) and metadata.strip():
        try:
            decoded = json.loads(metadata)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
    return {}


def _hash(record: dict[str, Any], field: str) -> str | None:
    value = record.get(field)
    if value is None:
        value = _load_metadata(record).get(field)
    if value is None or isinstance(value, (dict, list)):
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _hash_eligible(record: dict[str, Any] | None, label: str) -> bool:
    if record is None:
        return False
    if label != "framebuffer":
        return True
    return _load_metadata(record).get("framebuffer_comparison_eligible", True) is not False


def _record_id(record: dict[str, Any]) -> str:
    # Legacy summaries do not have stable IDs. Prefer the display name so a
    # summary can still be compared with its normalized-results counterpart.
    value = record.get("name") or record.get("id") or record.get("test_id")
    if value is None or not str(value).strip():
        raise InputError("record has no id, test_id, or name")
    return str(value).strip()


def _records(document: Any) -> list[dict[str, Any]]:
    if isinstance(document, list):
        records = document
    elif isinstance(document, dict):
        records = document.get("records")
        if records is None:
            records = document.get("results")
    else:
        records = None
    if not isinstance(records, list):
        raise InputError("expected a JSON array or an object containing records/results")
    if not all(isinstance(record, dict) for record in records):
        raise InputError("every record must be a JSON object")
    return records


def _resolve_input(path: Path) -> Path:
    if not path.is_dir():
        return path
    for name in ("normalized-results.json", "results.json", "summary.json"):
        candidate = path / name
        if candidate.is_file():
            return candidate
    raise InputError(f"no supported result file found in directory: {path}")


def load_run(path: str | Path) -> tuple[Path, dict[str, dict[str, Any]]]:
    source = _resolve_input(Path(path))
    try:
        document = json.loads(source.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise InputError(f"cannot read {source}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"invalid JSON in {source}: {exc}") from exc

    indexed: dict[str, dict[str, Any]] = {}
    for record in _records(document):
        record_id = _record_id(record)
        if record_id in indexed:
            raise InputError(f"duplicate record id in {source}: {record_id}")
        indexed[record_id] = record
    return source, indexed


def compare_runs(baseline_path: str | Path,
                 candidate_paths: list[str | Path]) -> dict[str, Any]:
    baseline_source, baseline = load_run(baseline_path)
    comparisons = []
    overall_pass = True

    for candidate_path in candidate_paths:
        candidate_source, candidate = load_run(candidate_path)
        missing = sorted(set(baseline) - set(candidate))
        extra = sorted(set(candidate) - set(baseline))
        rows = []
        checked = 0
        mismatched = 0

        for record_id in sorted(set(baseline) | set(candidate)):
            base_record = baseline.get(record_id)
            run_record = candidate.get(record_id)
            row: dict[str, Any] = {"record": record_id, "hashes": {}}
            for label, field in HASH_FIELDS:
                expected = _hash(base_record, field) if base_record else None
                actual = _hash(run_record, field) if run_record else None
                eligible = expected is not None and _hash_eligible(base_record, label)
                if eligible and not _hash_eligible(run_record, label):
                    actual = None
                match = (actual == expected) if eligible else None
                if eligible:
                    checked += 1
                    if not match:
                        mismatched += 1
                row["hashes"][label] = {
                    "checked": eligible,
                    "match": match,
                    "expected": expected,
                    "actual": actual,
                }
            rows.append(row)

        if checked == 0:
            verdict = "UNVERIFIED"
        elif missing or extra or mismatched:
            verdict = "FAIL"
        else:
            verdict = "PASS"
        overall_pass = overall_pass and verdict == "PASS"
        comparisons.append({
            "candidate": str(candidate_source),
            "verdict": verdict,
            "checked_hashes": checked,
            "mismatched_hashes": mismatched,
            "missing_records": missing,
            "extra_records": extra,
            "records": rows,
        })

    return {
        "schema_version": 1,
        "baseline": str(baseline_source),
        "verdict": "PASS" if overall_pass else "FAIL",
        "comparisons": comparisons,
    }


def render_human(report: dict[str, Any]) -> str:
    lines = [f"BASELINE {report['baseline']}"]
    for comparison in report["comparisons"]:
        lines.append(f"RUN {comparison['candidate']}")
        for row in comparison["records"]:
            values = []
            for label, _ in HASH_FIELDS:
                check = row["hashes"][label]
                value = "1" if check["match"] is True else "0"
                if not check["checked"]:
                    value = "-"
                values.append(f"{label}={value}")
            lines.append(f"  {row['record']} " + " ".join(values))
        lines.append(
            "VERDICT " + comparison["verdict"]
            + f" checked={comparison['checked_hashes']}"
            + f" mismatch={comparison['mismatched_hashes']}"
            + f" missing={len(comparison['missing_records'])}"
            + f" extra={len(comparison['extra_records'])}"
        )
    lines.append(f"OVERALL {report['verdict']}")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare one baseline with one or more xemu-perf result files.")
    parser.add_argument("baseline", help="baseline JSON file or run directory")
    parser.add_argument("candidates", nargs="+",
                        help="candidate JSON files or run directories")
    parser.add_argument("--json-out", type=Path,
                        help="also write the complete machine-readable report")
    parser.add_argument("--json", action="store_true",
                        help="write machine-readable JSON to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = compare_runs(args.baseline, args.candidates)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(json.dumps(report, indent=2) + "\n",
                                     encoding="utf-8")
    except (InputError, OSError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(render_human(report))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
