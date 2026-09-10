# PR70 review repair: focused host validation

The common cleanup now guards absent metadata, frees every owned name, frees the metadata and backing buffer, and zeros the layout. Failed construction and normal destruction both call it for ordinary uniforms and push constants. This repairs the PR70 partial-cleanup defect and the inherited backing-allocation omission tracked in Mainkill1/xemu#69.

| Check | Result | Scope |
| --- | --- | --- |
| Ownership states | 6/6 pass | Empty, absent metadata, absent backing, partial names, zero members, complete uniform/push pair |
| Repeated complete teardown | 256 pairs pass | Each layout cleared twice; ASan/UBSan/LSan enabled |
| Cache tests | 13 groups pass | Production cache implementation |
| Structural rejection | 10 new cases + repaired existing source-limit case | Enclosing checksum valid; live preexisting entry retained after rejection |
| Coverage | Deep rejection branches reached | Not merely rejection at the outer checksum |

The malformed SPIR-V header case also carries the corrected record checksum. The independent fixture checksum has a literal known-value check and an untouched positive control. Functional cache records are storage fixtures, not executable GPU shaders.

## Reproduce

From the product source root with Clang and GLib development files installed, enable the AddressSanitizer runtime option `detect_leaks` with value `1` (also recorded in the manifest):

```sh
mkdir -p review-checks
clang -std=gnu11 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -fno-omit-frame-pointer -I. \
  $(pkg-config --cflags glib-2.0) tests/unit/test-xbox-vk-uniform-layout.c \
  $(pkg-config --libs glib-2.0) -o review-checks/test-uniform-layout
review-checks/test-uniform-layout
clang -std=gnu11 -O1 -g -Wall -Wextra -Werror \
  -fsanitize=address,undefined -fno-omit-frame-pointer -I. \
  tests/unit/test-xbox-vk-spirv-prewarm.c \
  hw/xbox/nv2a/pgraph/vk/spirv-prewarm.c -o review-checks/test-spirv-prewarm
review-checks/test-spirv-prewarm
```

The maintained Meson targets are `test-xbox-vk-uniform-layout` and `test-xbox-vk-spirv-prewarm`. [Manifest](manifest.json) pins the source, toolchain, binaries, inputs and limits. Windows build, full-emulator failures/recovery, cache eviction, renderer lifecycle and paired gameplay qualification remain pending. Earlier b14 runtime results do not qualify this repair.
