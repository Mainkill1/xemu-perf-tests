# Reproduction fragment: PTIMER negative-fixture unit build

Use an owned checkout and an owned cache. This fragment builds only the PTIMER unit target; it does not run the Windows executable.

```sh
build_checkout=/path/to/owned/xemu-checkout
build_cache="$build_checkout/.build-cache"
toolchain_image='ghcr.io/xemu-project/xemu-win64-toolchain-gcc@sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2'

# build_checkout must be bd1fecb93353272dda2a810991e28945de35b665 plus the fixture patch:
# 8ffef2c2af6e35da01b3464d97a6a2e2f19185d3f141b2443ddef0fec833962b
# Ensure the project’s DSP fallback archive is already available if the image
# cannot fetch it during Meson configuration.

docker run --rm -v "$build_checkout:/src" -v "$build_cache:/xemu-cache" -w /src "$toolchain_image" \
  bash -euc './configure \
    --extra-cflags="-DXBOX=1  -Wno-error " \
    --extra-ldflags= \
    --target-list=i386-softmmu \
    --cross-prefix=x86_64-w64-mingw32.static- \
    --static \
    --extra-cflags="-flto-incremental=/xemu-cache/lto -flto-partition=cache" \
    -Db_lto=true -Dx86_version=3'

# Build the unchanged requested target once. This creates libqemuutil.a and is
# expected to stop at the target link with unresolved QAPI/QOM/trace symbols
# because the thin archive lacks a GCC-aware LTO index. Preserve this log.
set +e
docker run --rm -v "$build_checkout:/src" -v "$build_cache:/xemu-cache" -w /src "$toolchain_image" \
  ninja -C build -j12 tests/unit/test-xbox-nv2a-ptimer.exe
first_link_status=$?
set -e
test "$first_link_status" -ne 0

# Reindex only the owned generated archive. Record that its member list is
# unchanged and that the regenerated archive map is nonempty before retrying
# the exact same target.
docker run --rm -v "$build_checkout:/src" -w /src "$toolchain_image" bash -euc '
  AR=/usr/local/mxe/usr/bin/x86_64-w64-mingw32.static-gcc-ar
  NM=/usr/local/mxe/usr/bin/x86_64-w64-mingw32.static-gcc-nm
  RANLIB=/usr/local/mxe/usr/bin/x86_64-w64-mingw32.static-gcc-ranlib
  "$AR" t build/libqemuutil.a > build/members.before
  test "$(wc -l < build/members.before)" -eq 499
  "$RANLIB" build/libqemuutil.a
  "$AR" t build/libqemuutil.a > build/members.after
  cmp build/members.before build/members.after
  "$NM" --print-armap build/libqemuutil.a > build/armap.after
  test -s build/armap.after
'

docker run --rm -v "$build_checkout:/src" -v "$build_cache:/xemu-cache" -w /src "$toolchain_image" \
  ninja -C build -j12 tests/unit/test-xbox-nv2a-ptimer.exe

sha256sum "$build_checkout/build/tests/unit/test-xbox-nv2a-ptimer.exe"
```

For the recorded build, the binary SHA-256 is `4c86dba42881c8c0d17fe729e0a60e1a78927d1a91e769f6f210d196bb3ea4f8`. The complete comparable source-input hashes are: `ptimer.c` `f1bf4ddd3e87232f9eaf1f00c7043830606c71c23847cd15cca74794f0c034a0`; base fixture `93c9c57b6f1a521ac4a77247fc918f8538a2f8a638ecb00e6a177b7c2caaf6c4`; overlay fixture `414657abbc84f1983917aab1069d1ef9a68870ee6111bd9ad1492072c111fed9`; stubs `cb742a6dd64547c510a582f4c2c09708fc00906d61953126151dec4e237e754a`; shim `72f115849e6492781d1bac53d5a8da3795f87fd1187ad50cb934b3c586684f37`; and Meson file `3ad8ef5b74d6279e3d7e3dafe3c65c1654fc080f757dc56340aefa3b05d0d6e1`. This fragment intentionally makes no timing, benchmark, or native-result claim.
