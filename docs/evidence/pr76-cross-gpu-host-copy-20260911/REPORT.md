# PR76 cross-GPU host-copy qualification

**Status:** Ready to Integrate

**Product PR:** [Mainkill1/xemu#76](https://github.com/Mainkill1/xemu/pull/76)

**Issue:** [Mainkill1/xemu#72](https://github.com/Mainkill1/xemu/issues/72)

**Stable baseline:** `9f618d6d8c4c446ef023955f3d4de22f661f61a4`

**Previous main:** `fc8c5dec9c1aa18883e74b57937d7ec90fdea074`

**Current candidate:** `a08c4d92916554f55f09231f525cda1f93b55129`

## Summary

PR76 fixes the black guest display produced when AMD is selected as the
Vulkan renderer while the window's OpenGL presentation context remains on
NVIDIA. The exact final candidate passes focused adapter selection, the full
maintained XISO correctness suite, PGR2 snapshot, PGR2 full start, and the
Morrowind snapshot on both adapters.

The NVIDIA shared path passes the incremental performance gate. Its sustained,
p95, and p99 results remain within 2% of previous main, it records no 75 ms
retail stalls, and its adverse single-run maximums remain within the published
previous-main run ranges. AMD host-copy presentation is functional, but its
performance is mixed and is not presented as an improvement. The AMD result
combines a different GPU, driver, and presentation transport, so it does not
isolate host-copy cost.

All percentages are **Improvement %**: positive values are favorable and
negative values are adverse.

## Source and build identities

| Role | Commit | Tree | Executable SHA-256 |
| --- | --- | --- | --- |
| Fixed baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` | Retained published reference | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Previous main | `fc8c5dec9c1aa18883e74b57937d7ec90fdea074` | Retained published reference | `5c27d5310add91901f5a132c38d250492abf3d5eed253c2e6fe8cf63fb764768` |
| PR76 | `a08c4d92916554f55f09231f525cda1f93b55129` | `11981a736703553349357cd89926b443901cadb9` | `91ca72bddb6ec21441ffbbf3ef5bdddeda84ab3b7768d1f29081dca07136c4b3` |

The candidate used the official Windows O2/full-LTO/x86-64-v3 profile with
assertions and DWARF retained. The separate debug image and ordered-symbol
artifacts are identified in [the build receipt](build-receipt.json). The
focused Windows device-selection unit passed.

The maintained XISO came from xemu-perf-tests
`61012b4e702fbb46a02d813e71f2159a109a1c29`; image SHA-256
`6b2161f1b4abab94648f3fa0ca8da893092bab1b63d7e139a2358eb0319d05ac`.

## Why this patch exists

The failing release selected AMD for Vulkan but created the OpenGL window and
presentation context on NVIDIA. Importing AMD's opaque external-memory handle
into the NVIDIA OpenGL context left xemu running with activity on both GPUs,
but the guest display was black.

The candidate compares Vulkan device/driver identity with the devices exposed
by the OpenGL context. A compatible match keeps the existing shared external
memory path. A mismatch copies the completed Vulkan display-composition image
to mapped host memory and uploads it to a normal OpenGL texture. This copy
includes the selected internal scale and PVIDEO composition.

| Area | Same-GPU path | Cross-GPU candidate path | Effect |
| --- | --- | --- | --- |
| Vulkan rendering | Selected Vulkan adapter | Selected Vulkan adapter | Unchanged ownership |
| Presentation | Shared external memory | Host readback plus OpenGL upload | Makes an incompatible adapter pair display correctly |
| OpenGL presenter | Window GPU | Window GPU | NVIDIA remains involved on this host |
| Extra copy | None | One host-mediated presentation copy | Compatibility cost to measure |

## Improvement convention

| Raw + | Raw metric direction | Improvement % |
| --- | --- | --- |
| `+good` | Higher is better, such as FPS or completed work | `100 × (candidate / reference - 1)` |
| `+bad` | Lower is better, such as frame time or resource use | `100 × (reference - candidate) / reference` |
| `N/A` | Context only or no desired direction | No percentage claim |

## Focused native result

Both strict UUID-selection runs used the exact final executable. They captured
the xemu client, parsed the atomic GPU-selection record, closed normally, and
left no xemu process running.

| Requested Vulkan GPU | Actual Vulkan GPU | GL presenter | Transport | Client output | Exit / cleanup |
| --- | --- | --- | --- | --- | --- |
| AMD Radeon Graphics | AMD Radeon Graphics | NVIDIA RTX 3070 Ti Laptop | `host_copy` | 1280×960, 22.819% sampled nonblack pixels | Graceful / PASS |
| NVIDIA RTX 3070 Ti Laptop | NVIDIA RTX 3070 Ti Laptop | NVIDIA RTX 3070 Ti Laptop | `shared` | 1280×960, 22.819% sampled nonblack pixels | Graceful / PASS |

The sampled captures are functionally equivalent title scenes. Their hashes
are retained, but the captures occurred at different animation instants and
are not claimed to be bit-identical.

## Full XISO result

Each run contains 157 catalog records. The inherited
`report_query.dma_range_guard` nonpass is the only nonpass in each run; it is
shared tree state outside PR76. Vulkan validation was active and reported zero
VUIDs.

| Vulkan adapter | Transport | Guest results | Output ledger | Validation | PR76 disposition |
| --- | --- | ---: | --- | --- | --- |
| NVIDIA | Shared external memory | 156 pass / 1 known inherited nonpass | NVIDIA ledger PASS | 0 VUIDs | PASS |
| AMD, first comparison | Host copy | 156 pass / 1 known inherited nonpass | 57 hashes differ from NVIDIA | 0 VUIDs | Cross-device comparison |
| AMD, AMD-qualified ledger | Host copy | 156 pass / 1 known inherited nonpass | AMD ledger PASS | 0 VUIDs | PASS |

The first AMD run has the same guest outcomes as NVIDIA while 57 raw
framebuffer hashes differ. Fifty-five of those records are ledger eligible;
two same-address queued observations are intentionally excluded from the
functional ledger. The second AMD run passes the device-specific AMD ledger.
This demonstrates repeatable device-specific output and does **not** establish
bit-identical cross-GPU rendering. The exact differing records are in
[xiso-output-differences.csv](xiso-output-differences.csv), and the complete
per-test results are in [full-xiso-results.csv](full-xiso-results.csv).

These XISO runs used a verified clean archive whose runner label was
`SOURCE_STATE=clean-archive`. The runner's timing admission accepts only the
literal `clean`, so the explicit dirty-build waiver was required. XISO timing
is therefore excluded; the runs qualify correctness only.

## NVIDIA performance result

The references are retained published medians; they were not rebuilt. Each
PR76 row is one exact-final-head run. `Cold` and `warm` are campaign phase
labels. PGR2 encountered a prepopulated persistent shader store in both phases,
so those rows measure reuse rather than a pure cold compile.

| Workload | Phase | Metric | Raw + | Baseline | Previous main | PR76 NVIDIA | vs baseline | vs previous main |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| PGR2 snapshot | Cold | FPS | `+good` | 29.139 | 29.492 | 29.499 | +1.234% | +0.023% |
| PGR2 snapshot | Cold | p95 | `+bad` | 40.795 ms | 39.596 ms | 39.785 ms | +2.476% | -0.477% |
| PGR2 snapshot | Cold | p99 | `+bad` | 44.896 ms | 43.602 ms | 42.865 ms | +4.524% | +1.690% |
| PGR2 snapshot | Warm | FPS | `+good` | 29.139 | 29.408 | 29.536 | +1.361% | +0.434% |
| PGR2 snapshot | Warm | p95 | `+bad` | 40.795 ms | 39.714 ms | 39.503 ms | +3.167% | +0.531% |
| PGR2 snapshot | Warm | p99 | `+bad` | 44.896 ms | 43.144 ms | 43.917 ms | +2.181% | -1.792% |
| PGR2 full start | Cold | FPS | `+good` | 30.000 | 30.000 | 30.000 | +0.000% | +0.000% |
| PGR2 full start | Cold | p95 | `+bad` | 33.482 ms | 33.563 ms | 33.532 ms | -0.149% | +0.092% |
| PGR2 full start | Cold | p99 | `+bad` | 34.253 ms | 33.814 ms | 33.764 ms | +1.428% | +0.148% |
| PGR2 full start | Warm | FPS | `+good` | 30.000 | 30.000 | 30.000 | -0.000% | -0.000% |
| PGR2 full start | Warm | p95 | `+bad` | 33.482 ms | 33.656 ms | 33.577 ms | -0.284% | +0.235% |
| PGR2 full start | Warm | p99 | `+bad` | 34.253 ms | 34.028 ms | 33.818 ms | +1.270% | +0.617% |
| Morrowind snapshot | Cold | cadence | `+good` | 24.448 | 24.373 | 24.167 | -1.148% | -0.843% |
| Morrowind snapshot | Cold | p95 | `+bad` | 47.413 ms | 47.759 ms | 47.612 ms | -0.420% | +0.308% |
| Morrowind snapshot | Cold | p99 | `+bad` | 52.773 ms | 53.384 ms | 52.781 ms | -0.015% | +1.130% |

All NVIDIA sustained, p95, and p99 comparisons are within 2% of previous main,
and all NVIDIA retail runs have zero intervals at or above 75 ms. Snapshot
warm's 57.787 ms maximum is 0.342% above the largest published previous-main
warm maximum (57.590 ms). Full-start warm's 45.161 ms and Morrowind's 63.712
ms maximums are within the published previous-main ranges. These facts support
an incremental **PASS** without claiming that PR76 makes the same-GPU path
faster. Full precision and maximum comparisons remain in
[retail-comparisons.csv](retail-comparisons.csv).

## AMD adapter result

| Workload | Phase | Metric | Raw + | NVIDIA shared | AMD host copy | AMD vs NVIDIA Improvement % |
| --- | --- | --- | --- | ---: | ---: | ---: |
| PGR2 snapshot | Cold | FPS | `+good` | 29.499 | 25.054 | -15.066% |
| PGR2 snapshot | Cold | p99 | `+bad` | 42.865 ms | 60.362 ms | -40.819% |
| PGR2 snapshot | Cold | Maximum | `+bad` | 48.526 ms | 343.260 ms | -607.373% |
| PGR2 snapshot | Warm | FPS | `+good` | 29.536 | 25.390 | -14.034% |
| PGR2 snapshot | Warm | p99 | `+bad` | 43.917 ms | 56.180 ms | -27.923% |
| PGR2 full start | Warm | FPS | `+good` | 30.000 | 29.987 | -0.043% |
| PGR2 full start | Warm | p99 | `+bad` | 33.818 ms | 33.995 ms | -0.523% |
| PGR2 full start | Warm | Maximum | `+bad` | 45.161 ms | 70.891 ms | -56.974% |
| Morrowind snapshot | Cold | cadence | `+good` | 24.167 | 27.717 | +14.688% |
| Morrowind snapshot | Cold | p99 | `+bad` | 52.781 ms | 47.237 ms | +10.504% |
| Morrowind snapshot | Cold | Maximum | `+bad` | 63.712 ms | 177.533 ms | -178.649% |

AMD snapshot performance is slower, PGR2 full start is nearly cadence capped,
and Morrowind has better central metrics but one 177.533 ms stall. Because the
comparison changes the Vulkan device, driver, and transport at once, the
result is a functional qualification with **mixed performance**, not an AMD or
host-copy performance benefit. NVIDIA still carries the OpenGL presentation
load on this system.

## Correctness and cleanup

| Gate | NVIDIA shared | AMD host copy |
| --- | --- | --- |
| Focused selection and visible output | PASS | PASS |
| Full maintained XISO | PASS for PR76 scope | PASS for PR76 scope with device-specific ledger |
| Vulkan validation | Active, zero VUIDs | Active, zero VUIDs |
| PGR2 snapshot | Functional and measurement complete | Functional and measurement complete |
| PGR2 full start | Functional and measurement complete | Functional and measurement complete |
| Morrowind snapshot | Gameplay admission and final image PASS | Gameplay admission and final image PASS |
| Focus / not-responding samples | 0 / 0 | 0 / 0 |
| Close and private writable-disk cleanup | PASS | PASS |

OpenGL renderer testing is not applicable to this adapter-selection patch:
the new setting selects a Vulkan device, and cross-device presentation uses
the existing OpenGL window only as the presenter.

## Excluded attempts

| Attempt | Emulator started | Reason excluded |
| --- | --- | --- |
| XISO clean-archive preflight | No | Runner source-state admission expected literal `clean`; subsequent correctness runs used the explicit waiver and remain timing-ineligible |
| Morrowind warm preflight | No | No persistent cache file existed yet; the controller stopped before launch, so no performance sample exists |

Neither preflight is counted as a run or result.

## Final disposition

| Decision | Result |
| --- | --- |
| PR76 correctness | **PASS** |
| NVIDIA incremental performance vs previous main | **PASS** |
| Cumulative context vs fixed baseline | Reported; no new 2% central/p95/p99 blocker |
| AMD functional qualification | **PASS** |
| AMD performance | **MIXED — no improvement claim** |
| Integration recommendation | **Ready to Integrate** |

## Published evidence

- [Manifest](manifest.json)
- [Build receipt](build-receipt.json)
- [Focused native runs](focused-runs.csv)
- [XISO run disposition](xiso-runs.csv)
- [Full XISO per-test results](full-xiso-results.csv)
- [Cross-device output differences](xiso-output-differences.csv)
- [All retail cells](retail-runs.csv)
- [All Improvement comparisons](retail-comparisons.csv)
- [PGR2 snapshot cells](pgr2-snapshot-runs.csv)
- [PGR2 snapshot comparisons](pgr2-snapshot-comparisons.csv)
- [Excluded attempts](excluded-attempts.csv)
- [Exact final XISO runner adaptation](tooling/run-suite-pr76.py)

Raw game images, writable disks, screenshots, private host paths, and raw
host-specific launch records are not published. The sanitized records retain
source/build identity, adapter and presentation selection, per-cell metrics,
shader-cache counters, guest outcomes, validation status, and cleanup status.
