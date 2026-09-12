# PR71: live route-lookup diagnosis and focused repair check

This is a **diagnostic-only** PGR2 Vulkan snapshot comparison on the Windows test host. Both 30-second Off/On pairs completed, progressed through guest frames, and left no xemu or trace process running. The pre-fix diagnostic source is `f7f404146f42b2971f5ca44634d2b7578d931266`; the post-fix diagnostic source is `fedf4b0fa32fd51613c6c388d03aaf8e4ce48185`. They instrument product heads `d21072b39fd3a84b06943977f5f441116f229b2e` and `03b0d11675892b10851f54b892bd912396ae5a93`, respectively. Exact trees, executable hashes, counts, and times are in [lookup-attribution.json](lookup-attribution.json).

| Timed path / guest frame (lower is better) | Before: Off | Before: On | After: Off | After: On |
| --- | ---: | ---: | ---: | ---: |
| Route selection calls | 3,078 | 3,078 | 503 | 504 |
| Route binding-probe hits | 0 | 3,078 | 0 | 503 |
| Final binding lookups | 504 | ~0 | 503 | ~0 |
| Route selection CPU | 0.179 ms | **1.445 ms** | 0.030 ms | **0.279 ms** |
| Shader binding CPU (includes route) | 4.925 ms | **5.922 ms** | 4.478 ms | **4.539 ms** |
| Pipeline preparation CPU (includes binding) | 10.356 ms | **11.299 ms** | 9.863 ms | **9.985 ms** |

The source-level cause is precise. A register-dirty hint triggered route selection around 3,078 times per frame, yet Hybrid Off needed only around 504 binding lookups. Before the repair, Hybrid On probed the full binding cache on *every* dirty hint, even when the newly derived `ShaderState` matched the specialized binding already in use. Almost all of those probes were hits. Probe and final-bind hashes matched; there was no hash-identity mismatch. The module-first idea proposed in the preceding [r4 diagnosis](../diagnostic-r4/README.md) is superseded: the module key also hashes a large union and is not the right first repair.

[Product PR #71](https://github.com/Mainkill1/xemu/pull/71) now compares the effective state before route selection. When a specialized binding is already correct, it keeps that binding; fallback bindings still reach the selector so a completed specialization can replace them. The existing later state comparison is reused, so this does not add a second full-state comparison to dirty draws. The Windows production-profile source compiled, and this diagnostic confirms the intended probe reduction from ~3,078 to ~503 per frame.

The pre-fix Hybrid On-versus-Off route cost was 1.266 ms/frame; after the fix it was 0.249 ms/frame. That is about **1.017 ms/frame of isolated route overhead removed** in instrumented runs. The shader-binding On-versus-Off gap narrowed from 0.997 to 0.061 ms/frame. These are *timed diagnostic regions*, not normal-run average-frame, p99, or FPS improvements. Full XISO and retail qualification on the new exact product head remain pending; PR71 stays draft. The earlier >80 ms cold snapshot spikes are still not assigned to this route path.

Raw frame telemetry remains on the test host in the separate `pr71-live-lookup-r5` and `pr71-live-lookup-r6` capture directories. No diagnostic binary is release-qualified.
