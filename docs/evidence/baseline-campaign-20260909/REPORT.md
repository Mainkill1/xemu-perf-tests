# Baseline benchmark campaign

The retained legacy comparison binary is [published with diagnostic symbols and source](https://github.com/Mainkill1/xemu/releases/tag/baseline-bd1fecb9-20260909). Its executable is reused; no baseline rebuild or main change occurred. It is not yet the selected normalized-cycle baseline. The [current XISO release](https://github.com/Mainkill1/xemu-perf-tests/releases/tag/suite-442ec11-20260909) has 149 leaf tests and five groups.

## Coverage and current decision

| Workload | OpenGL | Vulkan |
| --- | --- | --- |
| Full XISO | Two attempts invalid for performance; runner transport and guest oracle gates unresolved | Held pending shared transport repair |
| PGR2 fresh start | Complete baseline observation; no candidate comparison | Complete baseline observation; no candidate comparison |
| PGR2 snapshot | Complete baseline observation; no candidate comparison | Complete baseline observation; no candidate comparison |

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

The corrected snapshot and FreshBoot routes each completed two sequential
60-second retained-baseline cells. The following observations remain baseline
evidence only; they do not compare a candidate or establish a performance
result.

## PGR2 snapshot baseline observations

Both snapshot cells completed functional and measurement gates with a validated
configuration, zero focus-loss samples, zero ETW lost events/buffers, verified
unchanged snapshot seed, and completed disposable-private-HDD cleanup. They
share the source, tree, executable, snapshot, runner, capture, and launcher
hashes in [pgr2-snapshot.json](pgr2-snapshot.json). The capture's optional
profiling-symbol field records `source_ownership_valid=false`: no matching PDB
or build manifest was supplied to that capture. This does not replace the
separately preserved release identity: its source/tree/binary are published
with embedded DWARF/COFF, full source, function mapping, and the documented
source-line-resolution limitation.

| Renderer | Complete guest frames (QPC) | Guest frame average / p95 / p99 | Guest flip cadence (/s) | Host presentation cadence (/s) | Host present p95 |
| --- | ---: | --- | ---: | ---: | ---: |
| OpenGL | 1,708 | 35.122 ms / 42.308 ms / 46.086 ms | 28.519 | 59.996 | 29.8095 ms |
| Vulkan | 1,740 | 34.484 ms / 40.910 ms / 45.186 ms | 29.012 | 60.003 | 27.9362 ms |

The complete-frame counts are guest-frame intervals selected by QPC timestamp.
The guest flip and PresentMon figures are display-write and host-presentation
cadence respectively; **neither is rendered FPS**. Both runs have zero guest
stalls at the 75-ms threshold. The published hashes identify the local complete,
dispatcher, frame-summary, filter, lifecycle, and capture outputs without
uploading their raw records.

A one-time local visual check of each snapshot capture found a race HUD, a
stationary 0 MPH car, a 1:54 snapshot clock, and no pause overlay. It supports
only that the snapshot was at that race UI; it does not establish racing
progression.

## PGR2 FreshBoot baseline observations

Both FreshBoot cells completed after a 10-second BIOS allowance, the recorded
navigation sequence, a 30-second warmup, and a 60-second steady-state window.
They share the baseline binary/source identity with the snapshot cells; their
per-run input and source-output hashes are in [pgr2-fresh.json](pgr2-fresh.json).

| Renderer | Complete guest frames (QPC) | Guest frame average / p95 / p99 | Guest flip cadence (/s) | Host presentation cadence (/s) | Host present p95 |
| --- | ---: | --- | ---: | ---: | ---: |
| OpenGL | 1,800 | 33.343 ms / 33.822 ms / 36.059 ms | 29.991 | 59.998 | 19.0856 ms |
| Vulkan | 1,801 | 33.333 ms / 33.412 ms / 34.497 ms | 30.000 | 59.998 | 22.8483 ms |

Both FreshBoot cells record zero guest stalls at the 75-ms threshold, zero
focus-loss samples, zero ETW lost events/buffers, unchanged seed hashes, and
completed disposable-private-HDD cleanup. As above, guest flip cadence and
host presentation cadence are not rendered FPS.

The FreshBoot images show starting-grid/race UI, a stationary 0 MPH car, blank
or dashed lap clock, and no pause overlay. This supports boot-to-race UI only;
it does not demonstrate racing progression.

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

## Tracked follow-ups

| Finding | Tracker |
| --- | --- |
| Shared 16-byte report-write bounds | [xemu #60](https://github.com/Mainkill1/xemu/issues/60) |
| Four required PFIFO leaves not enabled by runner | [perf-tests #10](https://github.com/Mainkill1/xemu-perf-tests/issues/10) |
| Strict production-build full-suite transport and contract | [perf-tests #11](https://github.com/Mainkill1/xemu-perf-tests/issues/11) |

These findings remain separate. This campaign does not weaken the complete suite or convert correctness-only timings into performance evidence.
