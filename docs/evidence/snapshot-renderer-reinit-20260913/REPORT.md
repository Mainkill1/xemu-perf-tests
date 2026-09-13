# Live snapshot renderer reinitialization: negative experiment

The opt-in full renderer reinitialization is **not suitable for integration**. It does not clear Morrowind's controller-reconnect overlay, and it blocks a live PGR2 reload waiting for a framebuffer held by the UI. This is a research result, not a performance qualification.

## Scope and identities

| Item | Identity |
| --- | --- |
| Product base | `Mainkill1/xemu` `main` `9148241de690617ac0a21a26b41858585c1e3cab` |
| Research source | `research/snapshot-renderer-reinit` at `3e658fced88117f871a3bf7275bcb33cbb5ceeb1` |
| Main A/B executable | SHA-256 `796bf9b1adbe3073f62dc79bdf51b04f7aaf3e5841ad8a5bd057dfbcd4b3a2ef`, source through `071acddb17d0611051449e3c3b640afd593833a4` |
| Stage-trace executable | SHA-256 `fa24eda7bc50d39e5f57c84e568c03ab70d1408f5ea5e420daffe81b4a300845`, source through `3e658fced88117f871a3bf7275bcb33cbb5ceeb1` |
| Host | Windows 22H2, Ryzen 9 6900HX, NVIDIA RTX 3070 Ti Laptop GPU, Vulkan |
| Toolchain | xemu Win64 GCC toolchain image `sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2` |
| Workloads | Morrowind heavy-scene snapshot `vm-20260905015459`; PGR2 snapshot `vm-20260907142321`; isolated private HDD copies |

The A/B uses **one executable** with `XEMU_SNAPSHOT_RENDERER_REINIT=0` or `1`. It starts from a saved snapshot, advances the game, and then issues a live QMP `human-monitor-command` / `loadvm` in the same process. The existing snapshot controller resumes the original run and cleans its private disk. The traces use aggregate guest display-write cadence as a progression proxy, not displayed FPS.

The reused build directory embedded the older template commit `46779cb09520f7dcc8b3c8db7cf379fb5e62eeb4` in the executable's version banner. The production source overlay was that clean template plus the single file differing at current `main` (`vk/renderer.h`) and the research commits. The exact source and executable hashes above are the research identities; do not treat the embedded banner as an exact-head qualification.

## Live reload results

| Cell | Reinit | Outcome after live reload | Guest progression / tail | Cleanup |
| --- | --- | --- | --- | --- |
| Morrowind | Off | QMP running, controller-reconnect overlay remains | Fewer than two display writes in the 15 s window | Owned process closed; private HDD removed |
| Morrowind | On | Second Vulkan initialization completes; same controller-reconnect overlay | Fewer than two display writes in the 15 s window | Owned process closed; private HDD removed |
| PGR2 | Off | Reload and final image validation pass | 29.971 display writes/s; p95 41.056 ms; p99 45.133 ms | Owned process closed; private HDD removed |
| PGR2 | On | QMP reload times out before second Vulkan initialization | No valid post-reload performance window | Owned process closed; private HDD removed |
| PGR2 stage trace | On | Reproduces timeout; last completed stage is renderer flush | Waits at `framebuffer_in_use` before finalize/init | Owned process closed; private HDD removed |

The PGR2 stage trace reached `renderer locks held` and `renderer flush done`, then logged `waiting for framebuffer`. It did **not** reach `finalizing renderer`. The existing live renderer-switch path waits for the UI to release its borrowed framebuffer. That handoff did not finish while this live snapshot reload was stopped. The test establishes this blocking point, not the exact UI thread state or a general defect in ordinary renderer switching.

Both Morrowind final captures visibly showed the already tracked controller-reconnect prompt ([xemu #61](https://github.com/Mainkill1/xemu/issues/61)). The reinit path itself completed on the on cell. The outcome does not support a graphics-reset explanation for that prompt.

An initial `-loadvm` startup A/B also completed, but it did **not** exercise the live restore callback: startup `system/vl.c` calls `load_snapshot()` directly, whereas the live UI/HMP paths first enter `RUN_STATE_RESTORE_VM`. Its timing differences are excluded from this verdict.

## Recommendation

Do not enable full renderer reinitialization on snapshot restore. A future snapshot-specific repair should first define the UI framebuffer release/rendezvous contract so VM stop cannot wait on an owner that cannot progress. Separately, test whether any pre-restore GPU-surface readback is needed before RAM is replaced; the current source ordering makes that a candidate risk, but this experiment did not prove VRAM corruption. Preserve normal post-load dirty-state restoration and test any narrower change with a live reload, not only startup `-loadvm`.

The [research PR #92](https://github.com/Mainkill1/xemu/pull/92) retains the source and bounded trace excerpts. `results.json` retains the compact machine-readable outcome. No game media, snapshot disk, screenshot pixels, private paths, or raw trace files are published here.
