# PR #11 PGR2 tail attribution from retained CpuScheduler traces

## Verdict

The retained traces do **not** attribute a reproducible p95/p99 regression to PR #11's changed Vulkan paths.

The initially adverse fresh-start candidate run did not reproduce against the exact parent in the same campaign. Its worst in-phase frame contains no direct sampled leaf in PR #11's texture cleanup/upload, surface readback/access callback, draw-result propagation, or wait functions. The snapshot candidate is also better than the exact parent in the retained run, and its worst frame does not contain a concentrated PR #11 leaf cost.

This is a bounded negative attribution result, not a claim that PR #11 makes xemu faster. The exported stacks do not retain resolvable full xemu call-chain addresses at switch-out, so they cannot name the logical wait behind the one adverse fresh candidate frame.

## Exact identities

| Role | Source identity | Exact executable SHA-256 |
| --- | --- | --- |
| Fixed cycle baseline control | behavior source `c17591d59c270b352b72e648f5ed65e4b2a3e77e`, tree `6824a5aa4d9ca288ac96092dc9244684e995b08d` | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| PR #11 immediate parent | `c5a598a0ea42f96ea3c460321d31bdb8916328ed`; tested tree-equivalent build source `659ad30be0488e85bea0df9514a5e52a31fcf290` | `7be97adf32b0e9e56f80a00c17f82f211b46a908098ff8b81e55b6df8eebcd27` |
| PR #11 candidate | `19944268d97ecd92f2dcd820d6e151107833795b` | `13f61e7655a7b37ea51c282335b7540b48e92dc5980af0877be2e968eb571d9a` |

All traces report zero lost ETW buffers and zero lost ETW events. The offline exports used WPAExporter `11.7.383.39833`. No emulator run or new trace capture was launched for this attribution pass.

## Retained frame results

Positive Improvement % means a lower interval is favorable.

| Workload | Run | Guest p95 | Guest p99 | p99 improvement vs exact parent | Interpretation |
| --- | --- | ---: | ---: | ---: | --- |
| PGR2 fresh Vulkan | Candidate r1 | 34.006 ms | 35.339 ms | -1.67% | Initially adverse candidate observation |
| PGR2 fresh Vulkan | Candidate r2 | 33.716 ms | 34.406 ms | +1.01% | Adverse p99 did not reproduce |
| PGR2 fresh Vulkan | Exact parent r1 | 33.800 ms | 34.757 ms | reference | Same campaign parent |
| PGR2 fresh Vulkan | Fixed baseline r1 | not used for exact-head decision | 34.497 ms | N/A | Prior-day unchanged control |
| PGR2 snapshot Vulkan | Candidate r2 | 42.139 ms | 45.841 ms | +6.94% | Candidate observation is favorable |
| PGR2 snapshot Vulkan | Exact parent r1 | 43.540 ms | 49.262 ms | reference | Same campaign parent |
| PGR2 snapshot Vulkan | Fixed baseline host control | not used for exact-head decision | 46.044 ms | N/A | Unchanged control |

The OpenGL negative controls also moved materially between repeats despite PR #11 having no OpenGL product-path change. That run-to-run movement is consistent with scheduler/workload variance large enough to invalidate a one-run small-tail conclusion.

## Selected worst-frame intervals

The fresh export covers the common in-phase cluster at ETL time 16.5-17.5 seconds. The snapshot export covers 5.0-6.4 seconds, containing each selected run's worst frame. Frame boundaries were reconstructed from the retained monotonic frame log and ETL/steady-state UTC offset.

| Run | Selected interval | Frame interval | PFIFO sampled weight | PFIFO scheduled running | PFIFO waiting | PFIFO scheduler-ready |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fresh candidate r1 | 43.062 ms | 17.054011-17.097073 s | 12.481 ms | 10.607 ms | 32.344 ms | 0.110 ms |
| Fresh candidate r2 | 35.894 ms | 16.863212-16.899106 s | 9.004 ms | 10.397 ms | 25.362 ms | 0.135 ms |
| Fresh exact parent | 38.933 ms | 16.819836-16.858769 s | 10.997 ms | 10.437 ms | 28.353 ms | 0.143 ms |
| Snapshot candidate r2 | 59.122 ms | 5.405134-5.464256 s | 45.957 ms | 47.770 ms | 11.232 ms | 0.120 ms |
| Snapshot exact parent | 65.003 ms | 5.914246-5.979249 s | 48.537 ms | 51.166 ms | 13.628 ms | 0.209 ms |

`Waiting` above is the clipped last-switch-out to ready interval. It describes time not scheduler-ready; it does not identify a condition variable, lock, fence, driver wait, or guest-command starvation. The original fresh r1 frame has about four milliseconds more PFIFO logical wait than the parent's selected frame, but only 0.110 ms scheduler-ready time. That longer logical wait disappears in candidate r2.

## PR #11 path samples

Exact candidate and parent MinGW executables retain COFF/DWARF symbols. Leaf instruction addresses were converted to RVAs using each trace's runtime image base, then bounded by the exact PE `.pdata` extents and exact defined-text symbol map.

During each exact selected worst frame:

| Selected frame | Direct PR #11 changed-path leaf samples |
| --- | --- |
| Fresh candidate r1, 43.062 ms | None |
| Fresh candidate r2, 35.894 ms | None |
| Fresh exact parent, 38.933 ms | None |
| Snapshot candidate r2, 59.122 ms | `create_pipeline`: 2.000 ms; `pgraph_vk_surface_update`: 1.000 ms |
| Snapshot exact parent, 65.003 ms | None; one 1.000 ms leaf in unchanged `pgraph_get_texture_shape` |

Across the complete comparison windows:

| Path / semantic group | Fresh candidate r1 | Fresh candidate r2 | Fresh parent | Snapshot candidate r2 | Snapshot parent |
| --- | ---: | ---: | ---: | ---: | ---: |
| `texture_layout_free` containing upload extent, texture upload/create/bind | 0 ms | 0 ms | 0 ms | 0 ms | 0 ms |
| Vulkan `surface_access_callback`, surface download/wait | 0 ms | 0 ms | 1.000 ms | 0 ms | 0 ms |
| `create_pipeline` | 12.726 ms | 15.030 ms | 26.906 ms | 31.732 ms | 35.252 ms |
| Draw flush semantic path | 2.004 ms | 4.990 ms | 5.000 ms | 16.752 ms | 10.986 ms |
| Surface update/download-range/upload leaves | 4.005 ms | 5.007 ms | 3.001 ms | 7.069 ms | 16.937 ms |
| `begin_pre_draw` | 0 ms | 2.001 ms | 0 ms | 0 ms | 1.000 ms |
| Combined rows above | 18.734 ms | 27.028 ms | 34.907 ms | 55.553 ms | 64.176 ms |

The snapshot candidate has about 5.8 ms more direct sample weight in the renamed/internalized draw-flush extent than the parent over 1.4 seconds. It simultaneously has less weight in pipeline creation and surface work, a lower combined changed-path total, a shorter worst frame, and a better p99. This isolated sampling movement does not establish a regression. The function's larger candidate extent also includes newly propagated result branches, so direct leaf naming is not a cycle-accurate separation of those branches.

No candidate sample lands directly in:

- the upload extent containing the fixed 96-slot `texture_layout_free()` cleanup scan;
- `upload_texture_image`, texture creation/binding, or their failed-upload retry bookkeeping;
- Vulkan `surface_access_callback` and its new lock reacquisition;
- `download_surface_to_buffer`, surface-download completion wait, or framebuffer readback wait.

The changed failure-injection implementation compiles away in the exact Release build and cannot explain these ordinary frames.

## Scheduler comparison for the complete windows

| Window | Run | PFIFO running | PFIFO waiting | PFIFO scheduler-ready | Max single wait | Max scheduler-ready |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Fresh, 1.0 s | Fixed baseline | 301.605 ms | 694.181 ms | 4.214 ms | 13.306 ms | 0.029 ms |
| Fresh, 1.0 s | Exact parent | 304.835 ms | 691.561 ms | 3.604 ms | 15.314 ms | 0.036 ms |
| Fresh, 1.0 s | Candidate r1 | 299.039 ms | 697.113 ms | 3.848 ms | 15.842 ms | 0.034 ms |
| Fresh, 1.0 s | Candidate r2 | 311.545 ms | 683.491 ms | 4.425 ms | 14.376 ms | 0.035 ms |
| Snapshot, 1.4 s | Fixed baseline | 695.025 ms | 700.525 ms | 4.450 ms | 13.206 ms | 0.030 ms |
| Snapshot, 1.4 s | Exact parent | 688.362 ms | 706.919 ms | 4.719 ms | 16.221 ms | 0.058 ms |
| Snapshot, 1.4 s | Candidate r2 | 677.491 ms | 718.280 ms | 4.229 ms | 12.039 ms | 0.023 ms |

There is no scheduler-ready inflation in the candidate. The larger candidate snapshot waiting total is paired with less scheduled PFIFO execution and a lower maximum single wait; it is not evidence of host scheduler starvation or a PR #11 lock regression.

## What remains unresolved

The sampled export supplies one leaf address per sample. Full xemu stack frames are serialized as missing-image/unresolved entries. The precise scheduling export supplies ready and switch timing, but it does not supply a resolvable PFIFO switch-out call stack or a guest/backend wait reason. `Old Wait Reason` describes the thread displaced when PFIFO switches in; it cannot be used as PFIFO's preceding wait cause.

Therefore these ETLs can reject direct-hotspot and scheduler-ready hypotheses, but cannot distinguish the original r1 logical wait among:

- an empty PFIFO guest command queue;
- PGRAPH mutex contention;
- Vulkan fence/submit completion;
- surface-download completion;
- display/flip coordination;
- a driver or other condition-variable wait.

The precise missing evidence is one of:

1. A matched parent/candidate capture that retains ImageLoad events and raw full StackWalk instruction pointers for PROFILE, CSWITCH, and READYTHREAD, including the PFIFO switch-out stack, plus exact frame timestamps and matching binaries/symbols.
2. Low-overhead frame-correlated ETW events or aggregate duration counters around PFIFO queue sleep, PGRAPH lock acquisition, `pgraph_vk_finish`/fence wait, surface-download completion wait, and display/flip wait. Synchronous hot-path logging would invalidate the timing.

No retained Morrowind CpuScheduler ETL exists for the PR #11 candidate or exact parent. Morrowind function/wait attribution requires the same matched trace content; cadence/result/image files alone cannot provide it.

## Evidence

- `export-manifest.json` records SHA-256, size, row count, column count, terminal-record status, and malformed-row count for every admitted CSV.
- `symbols/` contains hash-bound exact defined-text maps for candidate, parent, and fixed baseline executables.
- `profiles/generated-cpu/` contains the process-filtered sampled and precise scheduler profiles used for the clean exports.
- Raw retained ETLs remain on the test host at the paths recorded in each `inputs/*/complete.json`; local compressed WPA exports are retained in `exports/*.tgz`.

All 14 admitted CSVs have uniform row shape and a complete terminal record. No product source, branch, PR, issue, test workload, or GitHub state was changed by this attribution pass.
