# PR71 second-pass source/build receipt (2026-09-13)

This receipt qualifies focused source behavior and a Win64 build. It is not a gameplay, GPU-validation, or performance result.

| Identity | Value |
| --- | --- |
| Product head | `e5feb422b5b1798e2bf1194290b8b7fc63900cdb` |
| Product-code head | `819acd04bc5717d12e99651086732a755743603f` (later commit changes trace documentation only) |
| Previous PR71 head | `8a280999ed782af6ffe26158aff9718ac3426d94` |
| Builder source foundation | `e6048469f7f461ea8f0c91a4efe98f8331c9b8ce`, overlaid with the exact changed product files; SHA-256 file identities matched the product branch |
| Toolchain | `ghcr.io/xemu-project/xemu-win64-toolchain-gcc@sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2` |
| Configuration | Win64, x86-64-v3, O2, full LTO, assertions, DWARF |
| Executable SHA-256 | `57974dad98842fcb3ecd0d3924813efcaa971a7e8f73d035cc9c0e25f9de0dc9` |

| Focused check | Result | Limit |
| --- | --- | --- |
| Win64 `qemu-system-i386w.exe` | Build/link passed | No runtime execution of the product binary |
| Route/runtime cases | 15/15 passed under Wine | Includes complete-route, uncovered tie-break, time gate, and safe cache reservation; does not exercise a GPU |
| Pipeline-worker cases | 8/8 passed under Wine | Includes deep recipe ownership and an empty-result flag; fake driver only |
| Test red control | New tests failed to compile before the corresponding APIs existed | Establishes that the added tests reached the new interfaces |

The renderer now keeps a complete fallback selected during temporary descriptor or staging rollover. A control-only update can reuse the last descriptor set at capacity. Stable fallback draws reuse the active executable, compare raw constant registers, and probe promotion no more than once per 16 ms. A complete specialized route short-circuits fallback probing. The background pipeline request reserves an exact cache node before driver work; a hard-full cache can use an old safely evictable node, while an in-flight or active binding stays pinned. Empty pipeline-result checks avoid taking the worker mutex.

The result does not establish an FPS or cold-tail improvement. First-use fallback construction, renderer-thread shader-module/layout/render-pass preparation, pipeline failure retry policy, and a per-frame rather than per-draw publication budget remain to be evaluated. The resource probe remains conservative; the normal descriptor path is responsible for recovering a temporary rollover. PR71 remains Draft / HOLD until exact-head GPU output and performance qualification are published.
