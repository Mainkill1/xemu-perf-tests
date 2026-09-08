# Offline XISO oracle revalidation

The host comparator previously compared a framebuffer-derived diagnostic count even when the guest explicitly declared that observation inapplicable. This blocked two otherwise matching OpenGL baseline reports (14 versus 13) and mislabeled the disagreement as a hash failure.

`utils/oracle_validation.py` preserves the existing sealed-report schema, content-hash verification and raw counts. Its comparison-only projection excludes `internal_oracle.failure_count` exclusively for the two inspected queued S3TC records, with the exact framebuffer/tile exclusions, reason, and regression-only provenance. All other record fields remain compared. Explicit FAIL status is rejected. Mismatches identify the field.

This narrow compatibility rule reconstructs the guest applicability contract from v1 normalized reports; it is not permission to ignore diagnostic counters generally. A new producer or contract requires its own review and tests. Source: `src/tests/game_load_composite_tests.cpp`, `RunS3tcSyncFactor` and `ValidateS3tcSyncFactorFramebuffer` at tested guest revision `baf221e339f40801fee9ddd3abf1e1a6d21a1f0a`.

## Run

Python 3.10 or newer; standard library only. Inputs are sealed `oracle-report.json` files from completed campaigns, not hand-edited result fragments.

```sh
python3 utils/revalidate_oracles.py --help
python3 utils/revalidate_oracles.py \
  --baseline baseline-1/oracle-report.json baseline-2/oracle-report.json \
  --candidate candidate-1/oracle-report.json candidate-2/oracle-report.json \
  --output new-revalidation
```

Use one backend, guest image and job identity per invocation. The tool verifies reports before projection, checks input byte hashes after comparison, and refuses an existing output directory. It writes a consensus and a compact audit containing original report IDs, input digests, retained diagnostic values, exclusions and candidate results. Failure exits nonzero; it does not relaunch xemu or retry a test.

## Verification

142 contract tests pass, including 18 host eligibility/regression cases. Before the repair, the new applicability test fails because of the count mismatch; field-specific diagnostic tests also fail. Negative controls cover applicable pixels/counts, deterministic work/source checksums, explicit failures, unsupported applicability contracts, and report tampering. CLI coverage verifies input preservation and refusal to overwrite output.

Existing same-build off/on reports from xemu Release `0edb216c23ab071042bb26005267d0c3816337cd` were revalidated offline:

| Backend | Baseline reports | Candidate reports | Records/report | Consensus and candidates | Input bytes |
|---|---:|---:|---:|---|---|
| OpenGL | 2 | 2 | 149 | PASS | Unchanged |
| Vulkan | 2 | 2 | 149 | PASS | Unchanged |

[OpenGL audit](evidence/oracle-applicability/opengl-revalidation.json), [OpenGL consensus](evidence/oracle-applicability/opengl-consensus.json), [Vulkan audit](evidence/oracle-applicability/vulkan-revalidation.json), [Vulkan consensus](evidence/oracle-applicability/vulkan-consensus.json).

Original failed receipts and raw reports remain retained. This corrects the offline output comparison; it does not change timing measurements, prove a speedup, qualify a new executable, or complete xemu PR #25. It does not modify the locked runtime runner. Subsequent comparisons should use this versioned tool explicitly rather than patching a deployed copy in place.
