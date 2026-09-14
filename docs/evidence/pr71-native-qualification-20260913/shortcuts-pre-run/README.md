# PR #71 pre-run source and focused-test receipt

Product source: `fa00907d08239657e5ec1ec19041df138ab6ae4b`

Product tree: `0ee676b3e4b5da8447b322772495fee3847fc703`

Previous published PR head: `be016b73e19524fab2ebb25ff91433ea4693ad7b`
Windows executable SHA-256: `6e8053816aef10597d7f0f4c597c348c5deada28acafb4247327bc80d137f116`

The first focused check used a source overlay and produced executable
`90d074c6…`; it was not used for native testing. The builder was then reset
to the exact clean published product commit and rebuilt. The executable hash
above is the exact-commit build used for the subsequent PGR2 diagnostic.

Toolchain: pinned Win64 GCC image
`ghcr.io/xemu-project/xemu-win64-toolchain-gcc@sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`.
Build command: `ninja -C build qemu-system-i386w.exe
tests/unit/test-xbox-vk-ubershader-runtime.exe
tests/unit/test-xbox-vk-hybrid-compiler.exe
tests/unit/test-xbox-vk-hybrid-pipeline-builder.exe
tests/unit/test-xemu-tweaks-config.exe -j 8`.
The focused executables were run under Wine with `WINEDEBUG=-all`.

| Check | Result | Scope |
| --- | ---: | --- |
| Win64 product build | PASS | Link and compile only |
| Ubershader runtime unit cases | 18/18 | Includes cold-route, late-publication, queue, dirty summary, snapshot invalidation |
| Hybrid compiler unit cases | 9/9 | Required/speculative lanes and ownership |
| Hybrid pipeline builder unit cases | 8/8 | Deep recipe, queue, failure and shutdown |
| Tweak configuration | PASS | Default, persistence, migration, live and restart behavior |

The individual focused test rows are in [focused-tests.txt](focused-tests.txt).

## First native diagnostic bracket

The exact-commit executable ran the PGR2 saved-race workload for 30 measured
seconds in each configuration. The capture showed an active race, all three
cells completed, and each xemu process and private HDD closed cleanly. Tracing
and PresentMon were disabled; this is guest-frame interval evidence from one
non-interleaved bracket, not an acceptance comparison.

| Configuration | Guest frames | Mean ms | P95 ms | P99 ms | Maximum ms | ≥75 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hybrid Off, shortcut Off | 876 | 34.251 | 40.869 | 46.342 | 57.388 | 0 |
| Hybrid On, shortcut Off | 868 | 34.558 | 40.801 | 44.548 | 96.517 | 1 |
| Hybrid On, shortcut On | 871 | 34.447 | 41.429 | 45.921 | 55.714 | 0 |

The single 96.517 ms event is not yet attributed. The shortcut run has a
lower maximum than unswitched Hybrid On but a worse p99 in this one bracket;
it does not prove a performance improvement. See the [sanitized result rows](pgr2-short-bracket.json).

The current XISO test image was rebuilt separately from perf-tests main
`0044091f59ca148ab3c0bc919add10729bfe0fe3`, tree
`b2dcfae1164d8a2d741be766ee43e6e767c14310`, ISO SHA-256
`a91fdcc7b87e609a98075dfe9b6225edccb00d6036cfed6a4d7ea644b53d7400`,
catalog SHA-256 `a0674f73cef85d43f1dba0ad2059b9fa076841a0f4b1084b59186cf4ffb3871e`,
with 159 records. Its full exact-head campaign is still pending in this
receipt. Prior retail and XISO data remain historical. PR #71 stays Draft /
HOLD until the latest XISO and paired PGR2 full-start/Morrowind performance
gates pass.
