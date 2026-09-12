# PR #71: isolated Vulkan draw-path diagnostic

This is a **single 30-second PGR2 snapshot pair** on the exact candidate executable from [the full qualification](../results-r1/README.md), using the same binary with `XEMU_VK_PERF_LOG` enabled, shader caching enabled, separate cold Hybrid Off/On profiles, and no ETW capture. It followed the finished 39-cell campaign; both captures passed gameplay admission, retained normal guest progression, and cleaned up emulator/trace processes. The first attempt was rejected before gameplay because it was launched outside interactive Session 1; this successful rerun used the interactive dispatcher and a fresh evidence directory.

| Diagnostic measurement | Hybrid Off | Hybrid On | On minus Off |
| --- | ---: | ---: | ---: |
| Guest frames | 872 | 865 | -7 |
| p99 guest-frame interval | 45.004 ms | 47.252 ms | +2.248 ms (adverse) |
| `pipeline_prepare` CPU / guest frame | 9.652 ms | 11.045 ms | +1.393 ms (adverse) |
| All Vulkan waits / guest frame | 10.655 ms | 11.205 ms | +0.551 ms (adverse) |
| Submit CPU / guest frame | 0.274 ms | 0.277 ms | +0.003 ms (adverse) |

The emitted per-frame telemetry contained roughly 4,760 pipeline-preparation calls per guest frame in both profiles. Across this window the median reported preparation CPU per frame was 9.855 ms Off and 11.111 ms On. This points to draw-path work in addition to any one-off pipeline creation, but it does **not** isolate shader binding, ubershader packing, driver pipeline compilation, and descriptor work; the event counter arrays for shader-binding/pipeline-cache attribution were zero in this build. The instrumentation itself adds cost. It cannot replace the completed no-telemetry performance gate, and the cold 667 ms event in that gate was not reproduced by this pair.

See the [sanitized comparison](pgr2-vk-telemetry-comparison.md) and [source/build and cleanup receipt](diagnostic-receipt.json). Raw per-frame JSONL remains on the controlled test box. The concrete follow-up is to time individual operations inside `pipeline_prepare`, tagged by route and whether the driver pipeline was created, before changing the fallback policy; the full XISO and three retail workloads must be repeated on any changed product head.
