# Issue 60 exact-head Windows build outcome

- Candidate commit: `05c149635b839e09bbe1c457f26f55ca4ad5be8b`
- Candidate tree: `f1479bd7e58371f8b03233b73bf239b93dd5a024`
- Profile: Windows x86-64, optimization 2, full LTO, x86-v3, debug information,
  unstripped, assertions enabled
- Focused unit: `test-xbox-pgraph-reports.exe` — Wine exit 0
- Result: **BUILD_AND_DEPLOY_COMPLETE**

## Build-host capacity recovery

The first link attempt failed when full-LTO assembler scratch writes under
`/tmp` reached the full host filesystem. The second attempt moved `/tmp` to a
bounded memory-backed filesystem, but the LTO object cache remained on the full
host filesystem and failed similarly. No C or Meson source failure was reported.

The successful third attempt reused the same exact configured and compiled
source tree and Meson options. Both `/tmp` and `/xemu-cache` used separate
bounded 2 GiB memory-backed filesystems. This changed build storage only; it did
not change product source or compiler options. Raw attempt logs remain private
builder evidence.

## Verified artifact hashes

| Artifact | SHA-256 |
| --- | --- |
| `xemu.exe` | `9a08f60052d50ffc714baac85bbe6d8d4a25aeea4a623f0394b21d0c2342fb09` |
| `xemu.exe.debug` | `56f8ded287507810b7b501eabf9edb52d5e78f8374a015f6f62f116071df5dae` |
| `xemu-symbols.txt.gz` | `48220c05074dcaf86f8f38ccedc9eba2eb25c11edeeeab14f932af1d00c97b25` |
| `test-xbox-pgraph-reports.exe` | `cb460eb5d568c0d4757c7fdd0aba0a52df24637ef33c1ae81bcd413b536ea4e1` |

The fixed baseline and previous-main binaries were not rebuilt. No native emulator,
benchmark, or test-host diagnostic session was started by this build lane.

## Deployment

All 18 deployed artifacts matched the verified source bundle (65,667,162 bytes total). Matching debug information and symbols are retained for diagnostics. Raw build logs and private deployment paths are excluded from this public summary.
