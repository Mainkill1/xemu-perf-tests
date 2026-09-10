# PR14 retail tail-latency checkpoint

This checkpoint compares xemu PR #14 commit
`a1645a8612b6222437e2da17915258412a9beee0` with the immediately preceding
`main` tree built from `19944268d97ecd92f2dcd820d6e151107833795b`.
The candidate and reference executables have SHA-256
`51f5d9087d70c4354e1e1c32604fb8465f05fb3e6cb1214c3919c72826a08ebe`
and `13f61e7655a7b37ea51c282335b7540b48e92dc5980af0877be2e968eb571d9a`.

The result is **HOLD**. Fresh-start PGR2 remained within the 2% gate on both
renderers. Vulkan snapshot maximum interval regressed in both interleaved run
orders: 12.59% in the primary order and 10.23% in the reverse repeat. Average,
p95, and p99 remained within 2%, and neither order recorded a stall. A mean or
percentile result cannot override the repeated worse maximum interval.

## Improvement convention

Positive Improvement % is favorable and negative is unfavorable. Cadence is
`+good`; interval and stall metrics are `+bad`.

## Candidate versus previous main

| Workload | Renderer | Order | Metric | Raw + | Previous main | Candidate | Improvement % | Gate |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| PGR2 fresh | Vulkan | Primary | Cadence (/s) | `+good` | 29.995 | 30.000 | +0.02% | PASS |
| PGR2 fresh | Vulkan | Primary | Average interval (ms) | `+bad` | 33.338 | 33.333 | +0.01% | PASS |
| PGR2 fresh | Vulkan | Primary | p95 (ms) | `+bad` | 33.594 | 33.477 | +0.35% | PASS |
| PGR2 fresh | Vulkan | Primary | p99 (ms) | `+bad` | 34.337 | 34.325 | +0.04% | PASS |
| PGR2 fresh | Vulkan | Primary | Maximum (ms) | `+bad` | 42.285 | 40.490 | +4.25% | PASS |
| PGR2 fresh | Vulkan | Primary | Stalls | `+bad` | 0 | 0 | +0.00% | PASS |
| PGR2 fresh | OpenGL | Primary | Cadence (/s) | `+good` | 30.000 | 30.000 | -0.00% | PASS |
| PGR2 fresh | OpenGL | Primary | Average interval (ms) | `+bad` | 33.333 | 33.333 | -0.00% | PASS |
| PGR2 fresh | OpenGL | Primary | p95 (ms) | `+bad` | 33.552 | 33.732 | -0.53% | PASS |
| PGR2 fresh | OpenGL | Primary | p99 (ms) | `+bad` | 34.302 | 34.325 | -0.07% | PASS |
| PGR2 fresh | OpenGL | Primary | Maximum (ms) | `+bad` | 43.343 | 41.737 | +3.71% | PASS |
| PGR2 fresh | OpenGL | Primary | Stalls | `+bad` | 0 | 0 | +0.00% | PASS |
| PGR2 snapshot | Vulkan | Primary | Cadence (/s) | `+good` | 29.073 | 28.965 | -0.37% | PASS |
| PGR2 snapshot | Vulkan | Primary | Average interval (ms) | `+bad` | 34.347 | 34.514 | -0.49% | PASS |
| PGR2 snapshot | Vulkan | Primary | p95 (ms) | `+bad` | 41.096 | 41.498 | -0.98% | PASS |
| PGR2 snapshot | Vulkan | Primary | p99 (ms) | `+bad` | 45.503 | 45.739 | -0.52% | PASS |
| PGR2 snapshot | Vulkan | Primary | Maximum (ms) | `+bad` | 63.236 | 71.198 | **-12.59%** | **FAIL** |
| PGR2 snapshot | Vulkan | Primary | Stalls | `+bad` | 0 | 0 | +0.00% | PASS |
| PGR2 snapshot | Vulkan | Reverse repeat | Cadence (/s) | `+good` | 29.313 | 29.197 | -0.40% | PASS |
| PGR2 snapshot | Vulkan | Reverse repeat | Average interval (ms) | `+bad` | 34.089 | 34.230 | -0.41% | PASS |
| PGR2 snapshot | Vulkan | Reverse repeat | p95 (ms) | `+bad` | 40.441 | 40.621 | -0.45% | PASS |
| PGR2 snapshot | Vulkan | Reverse repeat | p99 (ms) | `+bad` | 44.838 | 45.386 | -1.22% | PASS |
| PGR2 snapshot | Vulkan | Reverse repeat | Maximum (ms) | `+bad` | 60.175 | 66.329 | **-10.23%** | **FAIL** |
| PGR2 snapshot | Vulkan | Reverse repeat | Stalls | `+bad` | 0 | 0 | +0.00% | PASS |

Each value is the median of two runs for that build within the stated order.
Primary order was previous, candidate, candidate, previous. Reverse repeat was
candidate, previous, previous, candidate. The adverse maximum therefore
survived an order reversal.

## Candidate versus fixed cycle baseline

The fixed baseline evidence is reused; it was not rebuilt. Its source is
`9f618d6d8c4c446ef023955f3d4de22f661f61a4`, behavior source
`c17591d59c270b352b72e648f5ed65e4b2a3e77e`, and executable SHA-256
`3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b`.

| Workload | Renderer | Metric | Raw + | Baseline | Candidate | Improvement % | Gate |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| PGR2 fresh | Vulkan | Cadence (/s) | `+good` | 30.000 | 30.000 | +0.00% | PASS |
| PGR2 fresh | Vulkan | Average interval (ms) | `+bad` | 33.333 | 33.333 | +0.00% | PASS |
| PGR2 fresh | Vulkan | p95 (ms) | `+bad` | 33.412 | 33.477 | -0.19% | PASS |
| PGR2 fresh | Vulkan | p99 (ms) | `+bad` | 34.497 | 34.325 | +0.50% | PASS |
| PGR2 fresh | OpenGL | Cadence (/s) | `+good` | 29.991 | 30.000 | +0.03% | PASS |
| PGR2 fresh | OpenGL | Average interval (ms) | `+bad` | 33.343 | 33.333 | +0.03% | PASS |
| PGR2 fresh | OpenGL | p95 (ms) | `+bad` | 33.822 | 33.732 | +0.27% | PASS |
| PGR2 fresh | OpenGL | p99 (ms) | `+bad` | 36.059 | 34.325 | +4.81% | PASS |
| PGR2 snapshot | Vulkan | Cadence (/s) | `+good` | 29.012 | 28.965 | -0.16% | PASS |
| PGR2 snapshot | Vulkan | Average interval (ms) | `+bad` | 34.484 | 34.514 | -0.09% | PASS |
| PGR2 snapshot | Vulkan | p95 (ms) | `+bad` | 40.910 | 41.498 | -1.44% | PASS |
| PGR2 snapshot | Vulkan | p99 (ms) | `+bad` | 45.186 | 45.739 | -1.22% | PASS |

The preserved baseline did not record maximum intervals or worst-frame
samples. It cannot settle the maximum-interval gate. The same-session,
interleaved previous-main comparison above supplies that incremental gate.

## Decision and next test

No PR #14 speed claim is supported. Ordinary retail expansion is paused while
the repeated Vulkan snapshot spike is isolated. A matched CpuScheduler pair
reproduced the failure at guest frame 676: 63.563 ms for previous main and
74.741 ms for the candidate, or -17.59% Improvement. PFIFO spent 10.675 ms more
blocked waiting for CPU 0/TCG to produce work. It was not scheduler-ready delay
or a GPU fence wait. The trace did not sample a changed PR #14 texture function,
and previous main spent more sampled time hashing than the candidate. See
`trace/REPORT.md` for the exact attribution limits.

The next test is a matched opt-in Vulkan telemetry pair using the unchanged
executables and route. If per-frame pipeline, texture, submission, and fence
metrics still cannot attribute the delay, the three focused changes in PR #14
will be instrumented or built as separate candidates and measured one at a
time.

Morrowind and the remaining renderer/workload cells are pending; their absence
does not waive the reproduced snapshot failure. PR #14 remains draft and held.

## Evidence files

- `metrics.csv` contains the normalized table rows.
- Each campaign directory contains its sanitized receipt and analyzer output.
- Run receipts identify exact source, tree, executable, order, workload, and
  the ten worst intervals per run.
- `trace/REPORT.md` and `trace/attribution-summary.json` contain the matched
  scheduler result and its explicit attribution limit.

Every completed run reported successful workload admission and cleanup. No
xemu or trace process and no disposable private HDD remained after a campaign.
