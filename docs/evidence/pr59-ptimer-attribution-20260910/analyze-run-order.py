"""Describe first/second position in the retained PR59 pairs; no causal model."""

import hashlib
import json
import statistics
from datetime import datetime
from pathlib import Path


root = Path(__file__).resolve().parent
source = root / "runs.json"
runs = json.loads(source.read_text())
measured = [row for row in runs if row["phase"] == "measured"]
assert len(measured) == 20 and all(row["status"] == "VALID" for row in measured)
result = {
    "source_file": source.name,
    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "evidence_commit": "fec867ab048ef52c783a5582cd4045756655ffd4",
    "method": "Reorder each declared pair by actual execution position; descriptive association only",
    "percentage_reference": "First-position run, which may be baseline B or candidate AM",
    "improvement_convention": "Positive favorable; negative unfavorable. Cadence raw +good; intervals raw +bad.",
    "qualification": "No causal attribution or performance acceptance",
    "renderers": {},
}
for renderer in ("OPENGL", "VULKAN"):
    pairs = []
    for pair in range(1, 6):
        rows = sorted((row for row in measured
                       if row["renderer"] == renderer and row["pair"] == pair),
                      key=lambda row: row["index"])
        assert len(rows) == 2 and {row["build"] for row in rows} == {"B", "AM"}
        first, second = rows
        assert datetime.fromisoformat(first["completed_utc"]) < datetime.fromisoformat(second["started_utc"])
        improvements = {}
        for metric in first["metrics"]:
            raw_change = 100 * (second["metrics"][metric] / first["metrics"][metric] - 1)
            improvements[metric] = raw_change if metric == "cadence_hz" else -raw_change
        pairs.append({
            "pair": pair,
            "first_run": first["run_id"], "second_run": second["run_id"],
            "first_build": first["build"], "second_build": second["build"],
            "first_metrics": first["metrics"], "second_metrics": second["metrics"],
            "second_vs_first_improvement_percent": improvements,
        })
    summary = {}
    for metric in first["metrics"]:
        values = [pair["second_vs_first_improvement_percent"][metric] for pair in pairs]
        summary[metric] = {
            "second_worse_pairs": sum(value < 0 for value in values),
            "total_pairs": len(values),
            "median_second_vs_first_improvement_percent": statistics.median(values),
        }
    result["renderers"][renderer] = {"pairs": pairs, "summary": summary}
print(json.dumps(result, indent=2, allow_nan=False))
