# PR14 current-main cubemap qualification

This evidence qualifies xemu PR #14 commit
`a1645a8612b6222437e2da17915258412a9beee0` against previous `main`
`f738796284d374f1cf22b05a6f5f643268fc8ab0`. The candidate executable was
the official Windows O2/full-LTO x86-v3 debug/assert Release build with
SHA-256 `51f5d9087d70c4354e1e1c32604fb8465f05fb3e6cb1214c3919c72826a08ebe`.

The restored guest oracle came from xemu-perf-tests commit
`61012b4e702fbb46a02d813e71f2159a109a1c29`, tree
`f5499b106caba6edf79ab3f7445a46503708121c`. Its XISO SHA-256 was
`6b2161f1b4abab94648f3fa0ca8da893092bab1b63d7e139a2358eb0319d05ac`.
Every cell returned the exact 157-record catalog.

## Correctness result

| Build | Renderer | Expected cubemap result | Observed | Wrong samples | Vulkan VUIDs |
| --- | --- | --- | --- | ---: | ---: |
| Previous `main` | OpenGL | FAIL negative control | FAIL | 10/12 | n/a |
| PR #14 | OpenGL | PASS | PASS | 0/12 | n/a |
| Previous `main` | Vulkan | PASS | PASS | 0/12 | 0 |
| PR #14 | Vulkan | PASS | PASS | 0/12 | 0 |

The OpenGL negative control read face 0 for every 1x1 and 2x2 sample. The
candidate returned the expected red, green, blue, yellow, magenta, and cyan
face values at both logical sizes. Vulkan validation was active in both
Vulkan cells and emitted no VUIDs.

`report_query.dma_range_guard` remained the only other non-PASS result in
every cell. It is tracked separately as Mainkill1/xemu issue #60 and is not
part of PR #14.

## Performance interpretation

The per-leaf duration tables are diagnostic context only. These Release
builds used the documented live-marker waiver, so this full-XISO run does not
support a performance improvement or regression claim. PR #14 remains gated
on interleaved PGR2 and Morrowind runs that record average interval, p95, p99,
maximum interval, stall count, and the worst intervals.

## Preserved rejected attempt

The first launch refused to start because the suite's disposable
`work/test.img` remained from an earlier campaign. No xemu or trace process
was launched; the 8 GiB disposable image was then removed after a clean
process check.

The next attempt completed both OpenGL cells, but the harness rejected the
candidate result as `SOURCE_SHA`/`SOURCE_TREE` unknown. Source inspection
showed that `run-suite.py` reads only an adjacent `BUILD_INFO.txt`; the exact
binary and `verified-build.json` were already correct. The rejected receipt
is preserved as `identity-sidecar-rejected-receipt.json`. Adding the
hash-pinned sidecar fixed the identity contract without rebuilding or changing
the binary. The full four-cell matrix was then rerun in a fresh directory.

## Files

- `qualification-summary.json` is the compact machine-readable result.
- `full-xiso/receipt.json` is the exact accepted runner receipt.
- `full-xiso/oracle-matrix.csv` is the clean correctness table.
- `full-xiso/*-leaf-durations.csv` contains all leaf records for each cell.
- `full-xiso/*-runner-output.txt` preserves each runner transcript.
- `full-xiso/functional-hash-ledger.json` preserves deterministic output
  checks.
- `unit-results.json` records the 6/6 focused Windows unit result.
- `xiso-build-receipt.json` identifies the guest build.

All four cells and final cleanup reported no remaining owned xemu or trace
process and no disposable private HDD.
