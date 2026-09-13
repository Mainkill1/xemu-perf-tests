# PR71 complete-route implementation receipt (2026-09-13)

This is a focused build/source check, not a gameplay or performance result.

| Identity | Value |
| --- | --- |
| Product code commit | `f3716a5a5cc5da14d12d644582f7755b12f87ef5` |
| Product documentation head | `8a280999ed782af6ffe26158aff9718ac3426d94` (code unchanged) |
| Previous published PR71 head | `13b2dc07db9e3c6c0b7b16bc01da06c50c7b1744` |
| Builder | `10.0.100.1`, isolated Win64 Docker build |
| Toolchain | `ghcr.io/xemu-project/xemu-win64-toolchain-gcc@sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2` |
| Configuration | Windows x86-64-v3, O2, full LTO, assertions and DWARF |
| Built executable SHA-256 | `fef2e445738da606d83e036c66188c2dd565f17761978a55c6854280b8d912b2` |

The isolated builder was based on `e6048469f7f461ea8f0c91a4efe98f8331c9b8ce`. Every product file changed between that base and `f3716a5a` was copied from the exact product commit, and local/remote SHA-256 file manifests matched. The builder's embedded Git version can still identify its older checkout; use the commit and executable hash above to identify this build. The documentation-only `8a280999` commit did not change product code or require a rebuild.

| Focused check | Result | Scope |
| --- | --- | --- |
| Win64 `qemu-system-i386w.exe` | Build passed | Compilation/link only; no xemu runtime |
| Pipeline-worker fake-driver tests | 7/7 passed | Recipe ownership, failure, late result destruction, queue capacity, shutdown |
| Slow-frame trace tests | 2/2 passed | Threshold and ring overflow |
| Route/key runtime tests | 12/12 passed | Non-creating ready probes, route requirement, vertex-input counts, control ABI |

The Win64 executables were built by Ninja in the pinned container and run directly with host Wine. The container's Meson test launcher could not read this older build directory's Meson metadata, so it did not execute any tests; the direct Wine invocations above completed with exit status zero. The only reported compiler warnings were existing variable-shadow warnings in unchanged `vk/blit.c`.

The ready-route decision for Hybrid On requires a ready shader binding **and** matching graphics pipeline; an uncovered draw explicitly takes a synchronous path. A module completion does not cause specialized takeover. Missing specialized graphics pipelines can be built by a bounded worker and adopted without draw-thread `vkCreateGraphicsPipelines()` or pipeline-cache eviction. The trace distinguishes shader materialization, layout creation, render-pass lookup, worker submission/adoption, and uncovered draws.

Remaining gates are deliberate: no exact-head XISO, PGR2, Morrowind, cold-tail, Vulkan validation, or normal-run performance test was run for this receipt. First-time uncovered draws currently build one fallback synchronously; warm SPIR-V module materialization and pipeline-layout/render-pass setup can still happen on the renderer thread. A full pipeline cache can defer background adoption. These paths require attribution before claiming reduced cold tails or merging PR71.
