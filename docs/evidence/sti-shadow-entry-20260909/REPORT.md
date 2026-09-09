# STI shadow-entry experiment: held after focused captures

**Keep [xemu #55](https://github.com/Mainkill1/xemu/pull/55) on hold.** Both focused game captures passed, but the Vulkan comparison shows no established benefit: cadence changed +0.30% with mixed tail timings. OpenGL moved favorably in this single comparison. The pending-IRQ qualification gate in [issue #56](https://github.com/Mainkill1/xemu/issues/56) also remains open. No production integration or general speedup is claimed.

| Renderer / metric | Retained main baseline | Candidate | Observed change |
| --- | ---: | ---: | ---: |
| Vulkan cadence/s | 23.723116 | 23.793884 | +0.298% |
| Vulkan p95 interval, ms | 47.990 | 48.401 | +0.856% |
| Vulkan p99 interval, ms | 57.134 | 56.833 | -0.527% |
| OpenGL cadence/s | 32.798427 | 33.715426 | +2.796% |
| OpenGL p95 interval, ms | 38.098 | 36.597 | -3.940% |
| OpenGL p99 interval, ms | 42.848 | 41.611 | -2.887% |

These are NV2A display-write cadence proxies, not rendered FPS. They are one candidate capture per renderer compared with previously stored baseline observations. Recipe, snapshot, renderer and presentation settings match, but runs were not interleaved and occurred at different times; environmental drift and repeatability were not controlled by this pair. Signs identify observed direction, not statistical improvement/regression. No baseline executable was rebuilt or baseline performance test repeated.

## Change and source identity

Main base `bd1fecb93353272dda2a810991e28945de35b665`, tree `6824a5aa4d9ca288ac96092dc9244684e995b08d`, exactly matches the earlier tested APU candidate whose [records are reused](../main-apu-load-20260909/REPORT.md). Candidate `1a73c5bce07be278c2aedb298caedbfd85f32aa0`, tree `cc8747be077d31a338b731b23e28cab940d62c7f`, changes only STI translation in two files.

STI uses dynamic lookup to enter a TB keyed with the newly established interrupt shadow. The dispatcher return after the shadow clears remains mandatory for pending IRQ delivery. MOV/POP SS keep their previous path, and existing TF/RF and no-goto-pointer handling remain. The candidate contains no temporary counters, guest addresses or clock/IRQ policy changes. [Prior attribution](../main-cause-return-20260909/REPORT.md) identifies the polling loop that motivated the experiment. A cheaper empty-queue loop is not automatically a gameplay improvement.

Candidate executable SHA-256: `4ef7cb6305813b369c225b9c88dc8ba4150ea7b82a2812af7f3973c500d33175`. Retained baseline executable: `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b`. Both use the pinned O2/LTO options, symbols, assertions and QOM checks. The candidate build passed and was checked for absence of diagnostic counter strings.

## Completed checks and remaining gates

The draft and branch existed before candidate build/native testing. Independent source review approved this exact head for experimentation and found no blocking source defect. One unchanged 20-second Morrowind cell per renderer completed; both final scenes were inspected and showed expected outdoor bridge/buildings and crosshair without pause/reconnect overlays. Nonblack checks, unchanged seed and private-disk/process cleanup passed.

This is not an independent pixel/audio oracle, native pending-IRQ proof or release qualification. No CPU/GPU/power/RAM/VRAM telemetry, full XISO, PGR2 or new guest suite was run for this initial decision. The generic PC-style TCG kernel fixture cannot simply be passed to the stock Xbox-only machine build; issue #56 records a possible original test-ROM route and the required boundary/fault/debug controls.

Do not merge based on the favorable OpenGL rows. Preserve the branch and evidence; prioritize clearer Vulkan work. Further promotion requires a justified performance case plus real IRQ delivery and the remaining validation gates. The hold does not assert that the patch is incorrect or universally slower.

[Manifest](manifest.json), [machine-readable comparison](comparison.json), [Vulkan result](vulkan-run.json), [OpenGL result](opengl-run.json), [exact candidate patch](candidate.patch). Metrics are copied from the linked run records; each delta is `(candidate - baseline) / baseline * 100`. No game assets, private configuration or complete application logs are included.
