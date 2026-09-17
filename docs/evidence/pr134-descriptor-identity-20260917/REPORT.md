# PR #134 descriptor identity evidence

This record qualifies the narrow Vulkan descriptor-publication change in
`Mainkill1/xemu` PR #134. It does not qualify issue #86 as resolved.

## Exact identities

| Role | Product source | Executable SHA-256 |
| --- | --- | --- |
| Instrumented control | `f3977d6fb659c61bd24361436a97b8ab286e23df` | `adc5f320ed9d29c9e72097b2a2f17abbd8679c7925ff6918d2905d15210910e2` |
| PR #134 candidate | `1447f60091be4a1db4857e53cd6de691c5395c27` | `731fbb223afdd3e96ea2312ffa81bde3c117480fea0646c8eb0e4b84271051fd` |

The control is PR #134's construction parent
`3cb55dffdd46a31dae9066c59d3dacf3b2942795` plus only the schema-8
attribution commit. It does not contain product commit `c61a43b0bc`.

Both executables used the pinned Win64 GCC toolchain image
`ghcr.io/xemu-project/xemu-win64-toolchain-gcc@sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`
with Release, `-O2`, full LTO, x86-64-v3, assertions retained, and symbols not
stripped. The candidate tree was clean. The exact candidate also passed the
Win64 texture-binding test 5/5 and ubershader-runtime test 26/26 under Wine.

## Workload

- Host: dedicated Windows test system, interactive Session 1 through the named
  PowerShell pipe.
- GPU: NVIDIA GeForce RTX 3070 Ti Laptop GPU, driver 581.380.0.
- Renderer: Vulkan; validation and debug shaders disabled.
- Presentation: shared external memory initialized; DXGI swap failed and the
  recorded run fell back to `SDL_GL_SwapWindow`.
- Surface scale: default 1x; VSync default enabled.
- Advanced settings: Hybrid ubershaders and shader shortcut default disabled;
  the other established performance shortcuts retained their defaults.
- Snapshot: `vm-20260905015459`.
- Input: wait five seconds after QMP reports running, press Start, wait two
  seconds, press B, wait two seconds, then measure for ten uninterrupted
  seconds.
- Runner SHA-256:
  `fed0a35f9ae97e0ecf6727f2f3869a1226b9989026566d8f7a89765f25e44c4b`.
- Order: candidate, then instrumentation-matched control.
- Shader cache: the retained persistent cache was not disabled for this
  descriptor-focused snapshot.

The metric is NV2A guest display-write cadence, not displayed FPS. Both cells
passed the automated final-image oracle, preserved the seed image, deleted the
private HDD, and left no xemu or recorder process running.

## Result

All counter values below are normalized per admitted guest-frame record.
Reason counters can overlap and do not partition descriptor writes.

| Metric | Control | Candidate | Change |
| --- | ---: | ---: | ---: |
| Guest display-write cadence | 24.736/s | 25.594/s | +3.47% |
| p95 interval | 47.620 ms | 47.369 ms | 0.53% better |
| p99 interval | 52.584 ms | 53.527 ms | **1.79% worse** |
| Actual descriptor writes | 1155.129 | 1076.777 | 6.78% fewer |
| Descriptor reuse returns | 0.000 | 77.098 | +77.098 |
| Texture-change requests | 1155.129 | 951.719 | 17.61% fewer |
| Descriptor-capacity requests | 1.004 | 0.387 | 61.48% fewer |
| Surface uploads | 1.476 | 1.234 | 16.36% fewer in this cell |
| Surface upload data | 94.452 KiB | 79.000 KiB | 16.36% fewer in this cell |
| Queue submits | 7.827 | 6.777 | 13.41% fewer |
| `NEED_BUFFER_SPACE` sampled wait | 6576.992 us | 2589.699 us | 60.62% lower |
| `SURFACE_CREATE` sampled wait | 1217.919 us | 4670.309 us | **283.47% higher** |
| Descriptor-update inclusive region | 7180.214 us | 3148.195 us | 56.15% lower |
| Draw-flush inclusive region | 12379.839 us | 9489.973 us | 23.34% lower |
| All sampled Vulkan waits | 12151.964 us | 11544.926 us | 5.00% lower |

The candidate's 316 surface uploads consisted of 315 color and one depth
upload. Their pending transitions were two new surfaces and 314 dirty-memory
detections; the run recorded no guest-write-callback cause and no forced upload.
The control's 366 uploads similarly consisted of 365 color and one depth
upload, with two new-surface and 364 dirty-memory causes.

The `SURFACE_CREATE` finish drains the prior main batch before the surface
source is prepared and uploaded. It is not the surface upload's GPU duration.
The actual auxiliary `surface_upload` wait was 77.471 ms total for the
candidate and 72.458 ms for the control. The longer pre-upload wait is
consistent with fewer earlier descriptor-capacity submissions leaving more
prior work at that boundary, but this pair alone does not prove causality.

## Cross-order interpretation

The earlier retained order ran current main first and the candidate second:

| Role | Cadence | p95 | p99 |
| --- | ---: | ---: | ---: |
| Current main, first | 26.170/s | 43.818 ms | 51.318 ms |
| Candidate, second | 25.635/s | 46.793 ms | 54.364 ms |

The reverse-order candidate remained close at 25.594/s, while the control
moved to 24.736/s. That exposes a material run/order influence in cadence. It
also leaves the tail result unresolved: candidate p99 was worse in both
comparisons. The code mechanism is proven, but this evidence does not establish
a mergeable end-to-end performance win.

## Disposition

Keep PR #134 in Draft / HOLD. The narrow comparison is functionally credible
and measurably removes descriptor work. It should not be merged as a Morrowind
performance fix while the p99 signal remains adverse and the wait has shifted
to the mandatory pre-surface-upload boundary.

No report ordering, surface ownership, descriptor pool sizing, GPU wait,
multi-batch lifetime, or upload semantics were changed in this patch.

## Files

- `analysis.json`: exact window-filtered totals and per-frame normalization.
- `candidate/result.json`, `control/result.json`: workload results.
- `candidate/vk-perf.ndjson.gz`, `control/vk-perf.ndjson.gz`: schema-8 raw
  frame telemetry.
- `candidate/hybrid-trace.csv.gz`, `control/hybrid-trace.csv.gz`: bounded
  slow-frame traces.
- `build/`: source/build identities and focused TAP results.
- `SHA256SUMS`: archive member integrity.
