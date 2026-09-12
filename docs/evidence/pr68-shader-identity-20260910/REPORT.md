# PR68 shader-identity diagnostic: incomplete shutdown flush

This diagnostic used xemu PR #68 source
`5341acd6719753e0e38e26acb4d995df06ce4ab3`, tree
`24767b54c7d20de2ac67d1f251257e934e7c9b27`, and Windows executable
SHA-256 `a4d86f5460e33b4c3b3d78d59664d69391d3131c6f79bf237cf8be6e3c7f78e3`.
The report tool was pinned to xemu-perf-tests
`f05cd73caef228d45637298dec31c54b853fb646`.

The PGR2 Vulkan snapshot reached gameplay and reproduced the known pipeline
preparation burst. The capture is **incomplete** because the deferred shader
identity records did not flush during normal application shutdown. It does not
qualify a performance change and cannot classify the shader-module misses.

## Diagnostic result

Interval metrics are `+bad`: a smaller value would be favorable. No
Improvement percentage is reported because this was a single instrumented
diagnostic build rather than a candidate comparison.

| Metric | Raw direction | Observed | Use |
| --- | --- | ---: | --- |
| Guest frames | `+good` | 1,753 | Gameplay admission |
| Average interval | `+bad` | 34.213 ms | Diagnostic only |
| p95 | `+bad` | 40.744 ms | Diagnostic only |
| p99 | `+bad` | 44.774 ms | Diagnostic only |
| Maximum | `+bad` | 65.303 ms | Diagnostic only |
| Stalls at or above 75 ms | `+bad` | 0 | Diagnostic only |
| Host presents | `+good` | 3,596 | Admission |

The worst interval occurred at guest frame 674. Its 65.303 ms interval
contained 42.437 ms of pipeline preparation across 4,808 calls and 53.518 ms
of draw flush work. This reproduces the phase targeted by PR #68.

## Missing classification

| Required shader result | State |
| --- | --- |
| First generated sources | Missing |
| Same-key repeats | Missing |
| Different-key, same-source repeats | Missing |
| Generation/compile/module/reflection time | Missing |
| Parser JSON, Markdown, and CSV | Correctly rejected the empty record set |

The second attempt explicitly supplied `XEMU_VK_SHADER_IDENTITY_TRACE=1` to
the owned xemu process. Normal window-close shutdown exited the process but
did not reach `shader_cache_finalize()`. The Vulkan renderer's pre-shutdown
hooks are empty, so the deferred record writer was never called.

## Required repair and rerun

Queue a one-shot trace flush through the Vulkan pre-shutdown hooks and execute
it on the renderer/PGRAPH producer thread after record production is
quiesced. The waiting shutdown thread must observe completion. Finalization
must remain idempotent, and tracing disabled must add no wait or draw-path
work.

After that diagnostic-only lifecycle repair is built, repeat this same PGR2
snapshot capture once. Choose a behavioral optimization only from the
completed key/source classification.

## Cleanup

Both attempts ended with zero owned xemu, PresentMon, WPR, WPA, or xperf
processes. Disposable private HDDs were deleted, the immutable seed hash was
unchanged, and no trace session remained.

`sanitized-incomplete-report.json` contains the complete portable result.
Raw captures, local paths, and guest assets are intentionally excluded.
