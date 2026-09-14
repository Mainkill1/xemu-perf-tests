# PR #71 pre-run source and focused checks

| Identity | Value |
| --- | --- |
| Product head | `be016b73e19524fab2ebb25ff91433ea4693ad7b` |
| Parent | `e5feb422b5b1798e2bf1194290b8b7fc63900cdb` |
| Win64 executable SHA-256 | `a63befa23a38093805a53713acaf659650f0fc0cc2063832b414244b9ad2a267` |
| Toolchain | `ghcr.io/xemu-project/xemu-win64-toolchain-gcc@sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2` |
| Build | Windows Release, O2/LTO product configuration; incremental Ninja build from the retained PR #71 build directory |
| Source transfer | Eight changed source/test files overlaid; `sha256sum -c` confirmed all eight match the product head |

The pre-run repair clears the active pipeline pin and finishes recorded work before shutdown cache flush. Promotion probing is paced per fallback binding, rollover draws can request specialization, and the uncovered-route helper now matches the production cold-route decision. A full shader-binding cache can evict an inactive binding instead of permanently blocking promotion. glslang preprocess, parse, and link failures return normally after cleanup rather than asserting.

| Focused check | Result | Scope |
| --- | --- | --- |
| Win64 product build | PASS | `qemu-system-i386w.exe` linked from the overlaid source |
| Runtime route/key tests | 15/15 PASS | Includes the corrected neither-binding uncovered-route expectation |
| GLSL compiler integration | 2/2 PASS | Real compiler/reflection ABI and invalid-GLSL failure return |
| Source transfer hashes | 8/8 PASS | All modified files matched the local product head |
| Whitespace check | PASS | `git diff --check` |

The build-directory Git metadata predates this commit; the product-source identity above is established by the eight matching file hashes and the retained parent. This is a focused structural check, not native GPU execution or performance qualification. Shutdown cleanup, cache saturation, and rollover scheduling have not yet been exercised in a live renderer. PGR2, Morrowind, full XISO, Vulkan validation, and frame-time comparisons remain pending before merge.
