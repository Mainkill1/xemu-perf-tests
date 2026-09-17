# Graphics descriptor capacity: focused comparison

**One measured Morrowind cell per renderer passed; no performance improvement is established.** [Draft #58](https://github.com/Mainkill1/xemu/pull/58) doubles the existing graphics descriptor batch from 1,024 to 2,048 on main, preserving fence completion before descriptor reuse.

| Metric | Renderer | Retained baseline | Candidate | Observed change |
| --- | --- | ---: | ---: | ---: |
| cadence (/s) | VULKAN | 23.723116 | 24.269446 | +2.303% |
| p95 (ms) | VULKAN | 47.990000 | 48.369000 | +0.790% |
| p99 (ms) | VULKAN | 57.134000 | 56.928000 | -0.361% |
| cadence (/s) | OPENGL | 32.798427 | 34.126817 | +4.050% |
| p95 (ms) | OPENGL | 38.098000 | 35.759000 | -6.139% |
| p99 (ms) | OPENGL | 42.848000 | 41.092000 | -4.098% |

Cadence is an NV2A guest display-write proxy, not rendered FPS. These use the same stored baseline recipe/settings/snapshot, but the baseline and candidate ran at different times without interleaving. Favorable OpenGL movement is also seen despite the change being Vulkan-only; this underscores that a single retained-baseline pair does not establish causality. Vulkan p95 is unfavorable. No baseline build or run was repeated.

## Correctness and scope

The exact candidate build and independent source/lifetime review passed. Both corrected-path cells reached QMP running, executed the existing Start/B sequence, completed 20-second windows, and passed their recorded nonblack-image, seed and private-disk cleanup checks. Final images were inspected and show the expected outdoor waterfront scene and crosshair without a pause/reconnect overlay. This is not an independent pixel/audio oracle or a Vulkan validation-layer campaign.

The candidate adds 1,024 descriptor sets,2,048 uniform-buffer descriptors and4,096 combined-image-sampler descriptors. Persistent and initialization-stack handle arrays also grow. Native startup succeeded on the tested host; CPU/GPU/RAM/VRAM and driver pool cost were not measured. No full XISO or PGR2 campaign was run.

## Retained failed setup attempt

The first Vulkan attempt used a renamed executable. The controller explicitly looks for xemu.exe, rejected process ownership before readiness/input, and later reported a generic QMP timeout. No measurement occurred. Its first cleanup also failed that check; exact identity-guarded termination subsequently removed the owned process and private disk. Staging the identical binary as xemu.exe corrected the contract for the measured cells. The original failure is retained in [sanitized evidence](rejected-staging-attempt.json); it is not a slow or failed rendering benchmark.

## Decision

Pause further optimization testing while [issue #40](https://github.com/Mainkill1/xemu/issues/40) is qualified against current main. The user requires a validated timer correction before any necessary baseline update, with a measured regression above 2% treated as a rejection gate. After that decision, return to a bounded fixed-work test of descriptor capacity. Do not promote from this small single-pair cadence movement or assume that the diagnostic wait time is removable. Full XISO, PGR2, resources and broader correctness remain integration gates. The main baseline is unchanged.

[Manifest](manifest.json) · [comparison](comparison.json) · [Vulkan result](vulkan-run.json) · [OpenGL result](opengl-run.json) · [diagnostic motivation](../vk-capacity-20260909/REPORT.md).
