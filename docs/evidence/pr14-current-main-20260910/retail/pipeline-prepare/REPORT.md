# PGR2 Vulkan pipeline-preparation attribution

Research PR #67 split the recurring slow `create_pipeline()` frame into
shader binding, key/cache work, pipeline-layout creation, and graphics-pipeline
creation. The exact Windows Release build used source
`86a2a9708b91b4b8d92548f05c5364c4f8967c2b`, tree
`c9aca7abac1295e600c15eae9de74d2f5472ae73`, and executable SHA-256
`73548608d5843d3b380aa0e7a0401ac36197bb5e7de7a29bc9eeadf98731d1db`.
Its focused texture-layout unit executable SHA-256 was
`2203cf9738c1a0640bb2f691088c3f309d5b7e4b9a806ab4d861dd38202e0c3d`;
all 7 tests passed on Windows.

Both repeat cells used the established PGR2 snapshot, Vulkan, B-3 input route,
a three-second warmup, a 60-second measurement, and all optional performance
controls disabled. ETL/WPR tracing was disabled. The counters change timing,
so these results locate work but do not qualify an optimization.

## Frame result

Positive Improvement % is favorable. Interval metrics are `+bad`. Both rows
use the same instrumented build, so no Improvement % is assigned.

| Metric | Raw + | Repeat 1 | Repeat 2 | Use |
| --- | --- | ---: | ---: | --- |
| Measured guest frames | `+good` | 1,717 | 1,717 | Admission |
| Average interval | `+bad` | 34.936 ms | 34.927 ms | Diagnostic |
| p95 | `+bad` | 42.131 ms | 42.602 ms | Diagnostic |
| p99 | `+bad` | 47.257 ms | 47.981 ms | Diagnostic |
| Maximum | `+bad` | 64.106 ms | 59.395 ms | Diagnostic |
| Stalls above 75 ms | `+bad` | 0 | 0 | Diagnostic |

Both cells completed gameplay admission and cleanup. Afterward, the host had
zero xemu/PresentMon/trace processes and zero disposable private HDDs.

## Slow-frame ownership

| `create_pipeline()` stage | Repeat 1, frame 665 | Repeat 2, frame 672 | Finding |
| --- | ---: | ---: | --- |
| Guest-frame interval | 64.106 ms | 59.395 ms | Recurring phase event |
| Complete `pipeline_prepare` region | 46.049 ms | 43.538 ms | Primary CPU region |
| Shader binding | 25.034 ms | 23.906 ms | Largest measured owner |
| `vkCreateGraphicsPipelines()` | 13.538 ms | 12.208 ms | Second measured owner |
| Pipeline key initialization | 0.123 ms | 0.114 ms | Small |
| Pipeline key hash | 0.167 ms | 0.198 ms | Small |
| Pipeline cache lookup | 0.187 ms | 0.187 ms | Small |
| `vkCreatePipelineLayout()` | 0.522 ms | 0.532 ms | Small |
| Summed measured stages | 39.571 ms | 37.145 ms | 86% and 85% of `pipeline_prepare` |
| Pipeline cache hits | 880 | 880 | Same event shape |
| Pipeline cache misses | 8 | 8 | Eight new pipelines trigger the burst |

The slow frame is a repeatable burst of eight new graphics pipelines. Shader
binding and `vkCreateGraphicsPipelines()` account for nearly all measured
pipeline-stage time. Key construction, hashing, LRU lookup, and layout creation
are not useful optimization targets for this event.

Earlier schema-v5 evidence recorded the same event on previous main at guest
frame 671: a 68.576 ms interval and 42.966 ms in `pipeline_prepare`. PR #14's
schema-v5 cell recorded it at frame 673: 66.080 ms and 41.867 ms. The event is
therefore a pre-existing PGR2 lag source, not proof that PR #14 introduced it.
The matched CPU trace also sampled glslang work during this phase, consistent
with shader generation inside the measured shader-binding owner; the schema-v8
counters do not yet divide shader cache lookup from module generation.

## Improvement route

The bounded performance targets are:

1. Avoid synchronous shader generation on a first-seen state where a validated
   cached module can be reused.
2. Avoid or move the synchronous `vkCreateGraphicsPipelines()` burst while
   preserving exact pipeline state, lifetime, and driver compatibility.

Possible mechanisms include a Vulkan shader-module cache backed by validated
SPIR-V and safe persistence of Vulkan pipeline-cache data. The evidence does
not yet choose an implementation. A behavioral patch needs its own focused
branch and draft PR before testing.

## Required qualification for any patch

A focused diagnostic is insufficient for acceptance. Every proposed patch must
run the complete per-change matrix on the exact head:

| Gate | Required coverage |
| --- | --- |
| Unit and fault checks | All affected production paths and cache/lifetime failures |
| Full XISO | Vulkan and OpenGL, complete catalog, output oracle and validation |
| PGR2 full start | Vulkan and OpenGL, gameplay admission and teardown |
| PGR2 snapshot | Vulkan and OpenGL, including the pipeline-burst phase |
| Morrowind | Vulkan and OpenGL, with verified unpause and gameplay scene |
| Performance | Average, p95, p99, maximum, and stalls versus previous main and fixed baseline |
| Resources | CPU, GPU, memory, cache growth, and lifecycle/cleanup |

No average-throughput gain can override a worse p95, p99, maximum interval, or
stall count. A regression in one valid test remains a failed gate until its
cause is understood and resolved.

## Decision

The recurring PGR2 spike is attributed to synchronous shader binding and
graphics-pipeline creation. This is a separate performance opportunity. It
does not clear PR #14, which remains **HOLD** under its ordinary uninstrumented
-20.78% Improvement tail result and still requires its full per-change suite.

`summary.json` contains sanitized identities, per-run totals, and worst-frame
attribution. Raw telemetry, screenshots, and local paths remain outside Git
history.
