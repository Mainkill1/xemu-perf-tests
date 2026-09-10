# PR14 opt-in Vulkan telemetry checkpoint

This diagnostic pair reused the exact previous-main and PR #14 executables,
snapshot, renderer, B-3 input, three-second warmup, 60-second measurement, and
disabled optional controls from the tail investigation. It enabled the existing
`XEMU_VK_PERF_LOG` path and collected no ETL.

The run completed and cleaned up, but it did **not** reproduce the prior
candidate maximum regression. Because enabled telemetry adds clock reads,
counters, and buffered JSONL output, these frame times are diagnostic and are
excluded from performance acceptance.

## Frame result

Positive Improvement % is favorable. All interval metrics are `+bad`.

| Metric | Raw + | Previous main | Candidate | Improvement % | Status |
| --- | --- | ---: | ---: | ---: | --- |
| Average interval | `+bad` | 34.834 ms | 34.585 ms | +0.72% | Diagnostic |
| p95 | `+bad` | 42.046 ms | 41.836 ms | +0.50% | Diagnostic |
| p99 | `+bad` | 47.754 ms | 46.536 ms | +2.55% | Diagnostic |
| Maximum | `+bad` | 68.576 ms | 66.080 ms | +3.64% | Did not reproduce |
| Stalls at 75 ms | `+bad` | 0 | 0 | +0.00% | Diagnostic |

Both maxima occurred at relative measured-frame index 156, which is the same
snapshot phase that dominated the no-telemetry and scheduler-trace runs.

## Affected-phase telemetry

The region order is surface update, draw flush, pipeline preparation, texture
binding, texture upload, and descriptor update.

| Metric | Raw + | Previous main | Candidate | Improvement % | Finding |
| --- | --- | ---: | ---: | ---: | --- |
| Draw flush CPU | `+bad` | 53.549 ms | 51.647 ms | +3.55% | Candidate lower |
| Pipeline preparation CPU | `+bad` | 42.966 ms | 41.867 ms | +2.56% | Candidate lower |
| Texture binding CPU | `+bad` | 2.987 ms | 3.290 ms | -10.14% | Candidate +0.303 ms |
| Texture upload CPU | `+bad` | 0.221 ms | 0.209 ms | +5.43% | Candidate lower |
| Descriptor update CPU | `+bad` | 6.049 ms | 4.618 ms | +23.66% | Candidate lower |
| Total sampled Vulkan waits | `+bad` | 10.374 ms | 10.060 ms | +3.03% | Candidate lower |
| Native BC upload count | N/A | 4 | 4 | N/A | Identical |
| Native BC source bytes | N/A | 961,312 | 961,312 | N/A | Identical |
| Native BC staged bytes | N/A | 961,312 | 961,312 | N/A | Identical |

Both builds made 4,808 texture-bind calls and seven texture-upload calls in
this phase. The candidate's extra 0.303 ms of aggregate texture binding is too
small to explain the earlier 7-11 ms tail difference, while the enclosing
pipeline and draw-flush regions were faster in this diagnostic run.

## Whole-run telemetry

| Metric per guest frame | Raw + | Previous main | Candidate | Improvement % |
| --- | --- | ---: | ---: | ---: |
| Vulkan wait time | `+bad` | 11,066.367 µs | 10,791.965 µs | +2.48% |
| Submit CPU time | `+bad` | 309.029 µs | 314.786 µs | -1.86% |
| Draw flush CPU | `+bad` | 20,330.126 µs | 20,070.891 µs | +1.28% |
| Pipeline preparation CPU | `+bad` | 9,497.456 µs | 9,284.125 µs | +2.25% |
| Texture binding CPU | `+bad` | 4,433.399 µs | 4,318.325 µs | +2.60% |
| Texture upload CPU | `+bad` | 85.840 µs | 84.866 µs | +1.13% |
| Descriptor update CPU | `+bad` | 6,572.771 µs | 6,409.371 µs | +2.49% |

## Attribution limit and next test

The existing telemetry does not count clamped cubemaps or separate declared
storage stride from sampled-level bytes. Equal aggregate BC upload bytes cannot
prove that no extra cubemap span was checked or hashed.

[Research PR #67](https://github.com/Mainkill1/xemu/pull/67) is the bounded
next step. It will add opt-in counters for clamped cubemap calls, storage and
sampled spans, surface checks, dirty checks, and hashing. The storage-span
hypothesis is rejected if that route is absent or its combined work stays below
1 ms in all tail frames. A 1-5 ms result is a contributor; at least 5 ms aligned
with the affected phase is required before building a behavioral A/B.

PR #14 remains held. This telemetry reversal prevents attributing the earlier
spikes to PR #14 without the missing counters, and it does not support calling
the candidate faster.
