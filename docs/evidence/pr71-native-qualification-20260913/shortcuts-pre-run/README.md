# PR #71 pre-run source and focused-test receipt

Product source: `fa00907d08239657e5ec1ec19041df138ab6ae4b`

Product tree: `0ee676b3e4b5da8447b322772495fee3847fc703`

Previous published PR head: `be016b73e19524fab2ebb25ff91433ea4693ad7b`
Windows executable SHA-256: `90d074c63d218d5ba03db171c4e88f9b6025f7e1993eabc9e39d7c4ae3b7dfb0`

The Win64 product executable was built from a source overlay: every tracked
path changed between the builder checkout `e6048469f7f461ea8f0c91a4efe98f8331c9b8ce`
and the product source above was copied from the product worktree before the
build. The builder checkout metadata still identifies `e6048469`; the binary
hash identifies this build, but its embedded version string is not the product
commit SHA. This is a focused source-equivalent build, not an exact-commit
release artifact.

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
No native GPU run, full XISO, PGR2, Morrowind, renderer validation-layer check,
or frame-time comparison was performed for this head. Prior retail and XISO
data remain historical and do not qualify this new code. PR #71 remains Draft
/ HOLD until exact-head functional and paired performance gates pass.
