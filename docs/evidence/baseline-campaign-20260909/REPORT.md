# Baseline benchmark campaign

The unchanged current-main baseline is [published with diagnostic symbols and source](https://github.com/Mainkill1/xemu/releases/tag/baseline-bd1fecb9-20260909). Its executable is reused; no baseline rebuild or main change occurred. The [current XISO release](https://github.com/Mainkill1/xemu-perf-tests/releases/tag/suite-442ec11-20260909) has 149 leaf tests and five groups.

## Coverage and current decision

| Workload | OpenGL | Vulkan |
| --- | --- | --- |
| Full XISO | Two attempts invalid for performance; runner transport and guest oracle gates unresolved | Held pending shared transport repair |
| PGR2 fresh start | Pending guarded launcher correction | Pending guarded launcher correction |
| PGR2 snapshot | Pending guarded launcher correction | Pending guarded launcher correction |

| Full-XISO observation | First attempt | Corrected interactive attempt |
| --- | ---: | ---: |
| Normalized records | 150 | 150 |
| Records reporting PASS | 149 | 149 |
| Records reporting FAIL | 1 | 1 |
| Required total | 154 | 154 |
| Live marker events | 0 | 0 |
| Overall acceptance | Infrastructure failed | Infrastructure failed |

These record counts are not a full-suite pass count: the required catalog contract did not pass. The failing record is `report_query.dma_range_guard`. Raw guest timings in the [first](attempt-1.json) and [corrected](attempt-2.json) normalized records are retained for diagnosis, explicitly ineligible for performance comparison. No aggregate speed, FPS, CPU or GPU result is claimed.

The first actual launch began at 2026-09-09 23:03 UTC in a noninteractive desktop and failed window attachment. The corrected attempt used interactive Windows Session 1 and reproduced the marker and query failures. The baseline source has no live-marker receiver, while this runner's default requires one; changing desktop sessions cannot satisfy that contract. The existing strict output-based validation mode is being reviewed. No marker waiver or guest-oracle waiver has been applied, and no further identical full-XISO attempt is scheduled.

PGR2 fresh-start and snapshot routes share an old launcher that unconditionally stops every xemu process. A focused parameterization/ownership correction is being prepared before those runs. Existing guards will retain private-disk and exact-process cleanup.

## Reproducibility

| Input | Identity |
| --- | --- |
| Current main | `bd1fecb93353272dda2a810991e28945de35b665` |
| Compiled baseline source | `c17591d59c270b352b72e648f5ed65e4b2a3e77e` |
| Shared tree | `6824a5aa4d9ca288ac96092dc9244684e995b08d` |
| Baseline EXE SHA-256 | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Test source | `442ec11b52ce1c9d7359825944bcbc2b5f524d07` |
| Test ISO SHA-256 | `3896df77a75fc35a6212f30b46cfd836fe65f86dbfc2004bd756c5fd7f1aacbe` |
| Catalog ID | `sha256:c5f65e25a9ca5581a55b92b73e1f9894bfb2082fd08cf79a175bd6cc94c50b8a` |
| Runner SHA-256 | `c478e3a38865de180f3751b88904bf18b152dd05208e773326979e3d7b65b64d` |
| Suite Python SHA-256 | `d932e5e2f324d57f392e8fd063dcf6d0185be8a664c57c6d24e7762ed02c28ca` |
| Configuration | OpenGL, scale 1, 64 MiB guest RAM, no warmup, multiplier 1, per-iteration completion, telemetry off, timeout 900 s |

The system Python initially lacked the suite dependency and failed before launching xemu. Both real attempts used the installed suite Python. Failed setup attempts are not counted as guest executions. PR #59 remains separate and unaccepted; this campaign report concerns the retained baseline.
