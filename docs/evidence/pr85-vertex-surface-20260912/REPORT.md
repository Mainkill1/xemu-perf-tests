# Morrowind Vulkan vertex/surface synchronization and report-wait attribution

**Follow-up diagnosis:** [Issue #86's report/TCG trace](issue86-deep-diagnosis/REPORT.md) found a zero-query clear-plus-report pair at every measured Vulkan `STALLED` fence. The measured median was 10.587 ms, while a separate CPU ETW capture found the guest CPU thread running for 9.865 of 10 seconds, with 48.0% of its samples in translated-block lookup. Guest-PC samples found a retry loop strongly concentrated during report stalls (22/26 near-stall versus 2/94 later samples); its status source still needs identification. A same-executable OpenGL snapshot reached 34.664 guest display writes/s versus 23.4–23.9 in three Vulkan diagnostic cells. This narrows the renderer gap but does not establish that early report publication would preserve the guest's GPU fence semantics; both product PRs remain drafts.

**Status: diagnostic progress, no accepted performance improvement.** Draft [product PR #85](https://github.com/Mainkill1/xemu/pull/85) removes false vertex-triggered surface readbacks. Draft [PR #83](https://github.com/Mainkill1/xemu/pull/83) is now stacked on #85 and changes only the graphics descriptor-set capacity. It retains the original one-line commit and adds a merge commit; its exact combined tree matches the build tested here. [Issue #84](https://github.com/Mainkill1/xemu/issues/84) tracks the false readback, and [issue #86](https://github.com/Mainkill1/xemu/issues/86) tracks the newly isolated report wait.

| Identity | Value |
| --- | --- |
| Previous-main runtime source | `6bf9e98cdee50fd73e936ff2bd5b485ce14ac4dc`; runtime-equivalent to current `main` `9148241de690617ac0a21a26b41858585c1e3cab` |
| Fixed cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; no new baseline measurement in this investigation |
| PR #85 source and executable SHA-256 | `2163208fdc49c7f6b4834bce98e6a11b494d4241`; `fdafe9acae32f1a189eff6cd270bdd6443571b7e33f870efaf9bfa1b2a22f0dc` |
| Combined source and executable SHA-256 | PR #83 head `5717357917abdd92e7c344d9e4f1b36b6fa61afa`, tree `b0de7c5381392859e82c06a421fd56ac963ae39e`; `5331d3712b90d6779283a0dd86950d899334f68ec8baca2a2b9dd47c15fe7142` |
| Combined base-to-head patch SHA-256 | `cfc0dca38c6c6f7f8bb8e71687bd1f9bd25a31d01d60604e8a4d454d842ce895`; builder diff matched the local tested tree |
| Previous-main executable SHA-256 | `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6` |
| Build profile | Pinned Windows GCC image digest `09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`, O2, full LTO, x86-v3, assertions and DWARF; `.debug_info` and `.debug_line` verified in both new executables |
| Test runner | SHA-256 `9994bd2d823e8557d39aef582fef8d7f37965d54caa52eaa09514e5d256307ed`; pinned snapshot and Start/B input, 10-second measured window |
| Evidence tooling | [`utils/summarize_vk_wait_reasons.py`](../../../utils/summarize_vk_wait_reasons.py); raw diagnostic streams retained on the test host and identified by hashes in the compact JSON |

Every completed cell reached the same snapshot, passed the existing final-image nonblack oracle, preserved the snapshot seed, deleted its private HDD, and left no emulator or trace process running. These short samples use guest display-write cadence, **not displayed FPS**. Their run order and size do not qualify an optimization.

## What changed in the measured Vulkan path

The earlier [PR #83 investigation](https://github.com/Mainkill1/xemu-perf-tests/pull/32) showed that page alignment made 7,906 original vertex requests appear to overlap a GPU-authored surface although none of those original byte ranges did. PR #85 makes the readback decision on the original ranges, retains page-aligned upload/dirty tracking, and forces an upload for a genuine surface intersection. It also invalidates the vertex mirror after any successful surface readback. The one-line #83 capacity change removes the premature 1,024-set descriptor-pool submission. Both are source changes; this report measures their interaction.

| Opt-in 10-second Vulkan counters | Previous main | PR #85 alone | PR #85 + #83 |
| --- | ---: | ---: | ---: |
| Measured guest frames | 242 | 244 | 237 |
| `NEED_BUFFER_SPACE` submits | 243 | 245 | **0** |
| `SURFACE_DOWN` submits | 193 | **1** | **1** |
| `STALLED` submits | — | 244 | 237 |
| Median `NEED_BUFFER_SPACE` fence wait/frame | 9.479 ms | 9.425 ms | **0** |
| Median `STALLED` fence wait/frame | — | 1.783 ms | **11.006 ms** |
| Median total sampled finish-fence wait/frame | 12.423 ms | 11.808 ms | **12.083 ms** |
| Median Vulkan queue submissions/frame | 6 | 4 | 3 |
| Median `draw_flush` region/frame | 16.404 ms | 15.250 ms | 5.797 ms |

The `draw_flush` region contains nested waits; its drop in the combined build is **time relocation**, not a 10 ms CPU saving. PR #85 removed nearly all measured `SURFACE_DOWN` submissions, but descriptor exhaustion remained. Adding #83 removed descriptor exhaustion, then the wait moved to `STALLED`. The combined capture had one `STALLED` submission per measured frame, with a median 11.006 ms fence wait. Source inspection finds the unique call in `pgraph_vk_process_pending_reports()`: FIFO idle with a nonempty report queue and active command buffer invokes `pgraph_vk_finish(... STALLED)`, which submits and waits before publishing occlusion-query reports. This is a *confirmed synchronization point*, not yet proof that the guest can safely see report results later.

## Short uninstrumented comparison

Positive **Improvement %** is favorable. Cadence is `+good`; intervals are `+bad`. These are single, sequential 10-second cells, so the percentages show direction only.

| Same-day Morrowind snapshot, Vulkan | Raw + | Previous main | PR #85 | PR #85 + #83 | Improvement #85 vs main | Improvement combined vs main |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Guest display writes/window second | `+good` | 23.674 | 23.996 | 23.966 | +1.36% | +1.23% |
| Guest interval p95 | `+bad` | 50.076 ms | 48.498 ms | 50.184 ms | +3.15% | -0.22% |
| Guest interval p99 | `+bad` | 55.904 ms | 59.161 ms | 59.056 ms | **-5.83%** | **-5.64%** |

PR #85's separate opt-in counter cell measured 24.380 display writes/s and p99 52.465 ms; the combined counter cell measured 23.676 writes/s and p99 57.129 ms. Diagnostic timing is not pooled with the uninstrumented cells. The uninstrumented p99 warning and absent sustained benefit keep both PRs in draft.

## Remaining gates and next causal question

- **Not run on these heads:** current full XISO suite (either renderer), Morrowind OpenGL, PGR2 snapshot/full start, 60-second counterbalanced Morrowind pairs, true-overlap and after-eviction vertex freshness oracles. Those are required before a merge decision. Historical baseline results are retained; no new baseline qualification is inferred.
- **Correctness risk:** marking `DIRTY_MEMORY_NV2A` after a GPU readback protects the vertex mirror but may cause extra surface upload work in other workloads. The XISO surface and vertex cases and upload counters must check it.
- **Performance question:** determine whether Morrowind reads queued occlusion reports immediately after FIFO idle. Measure `GET_REPORT`/clear commands, query counts, result-publication time, first guest read of each destination, and GPU execution separately. Only then design a deferred or async report-completion path with a correct guest-read fallback. Moving the `STALLED` fence wait without reducing total work is not a fix.

The paired source changes reduced the number of submissions, but did not materially improve the observed guest cadence. The remaining ~12 ms sampled finish-fence time per measured frame is now dominated by idle report retirement, while sampled vCPU/TB-dispatch work in the prior ETL remains a separate shared ceiling. No code in this evidence PR changes xemu runtime behavior.
