# PR76 cross-GPU host-copy qualification

PR76 head `c40375db7fc274dc097eae71c72d3ee6460dcce8` fixes the
black display seen when xemu renders with the AMD Vulkan adapter while its
OpenGL presentation context remains on NVIDIA. Focused native validation now
passes on both adapters. A 60-second PGR2 snapshot run now covers the NVIDIA
shared path and AMD host-copy path. Full XISO, PGR2 full-start, and Morrowind
snapshot qualification remain pending, so the PR remains draft.

## Cause and correction

The failing release selected AMD for Vulkan and loaded the AMD Vulkan driver,
while the OpenGL context and window remained on NVIDIA. Both GPU engines were
active, but importing the AMD opaque Win32 memory handle into the NVIDIA GL
context produced a black guest display.

The candidate compares the Vulkan device and driver UUIDs with every device
UUID and the driver UUID reported by the GL context. A compatible match keeps
the shared-memory path. A mismatch omits external-memory export/import, copies
the finished Vulkan display-composition image into mapped host memory, and
uploads that image to a regular GL texture. The copied image includes the
selected internal scale and PVIDEO composition.

## Source and build identities

| Role | Commit | Tree | Executable SHA-256 |
| --- | --- | --- | --- |
| Previous main / failing release | `fc8c5dec9c1aa18883e74b57937d7ec90fdea074` | — | `5c27d5310add91901f5a132c38d250492abf3d5eed253c2e6fe8cf63fb764768` |
| PR76 candidate | `c40375db7fc274dc097eae71c72d3ee6460dcce8` | `001ffaca2bc407d25c1519c4805a3765f899896f` | `4cacd9ddd20a6255fd845e871acf5c7cc04df777af10d35d0fcb4c0dcbbb8a46` |

The candidate used the official Windows O2/full-LTO/x86-64-v3 profile with
assertions, unstripped DWARF, a separate debug image, and ordered symbols. The
focused Windows device-selection unit exited successfully.

## Focused native result

Both runs used strict exact-UUID selection through the interactive Windows
desktop session. They captured the xemu client after 20 seconds, parsed the
candidate's atomic GPU record, closed xemu normally, and verified that no xemu
process remained.

| Requested Vulkan GPU | Actual Vulkan GPU | GL presenter | Transport | Client capture | Nonblack sample | Exit / cleanup |
| --- | --- | --- | --- | --- | ---: | --- |
| AMD Radeon(TM) Graphics | AMD Radeon(TM) Graphics | NVIDIA RTX 3070 Ti Laptop | `host_copy` | 1280×960, visibly correct | 22.819% | Graceful / PASS |
| NVIDIA RTX 3070 Ti Laptop | NVIDIA RTX 3070 Ti Laptop | NVIDIA RTX 3070 Ti Laptop | `shared` | 1280×960, visibly correct | 22.819% | Graceful / PASS |

The captures show the same rendered title scene. Their hashes differ because
the animated scene was sampled at different instants. Screenshots and guest
media remain private; `focused-runs.csv` retains dimensions, hashes, and pixel
sample counts.

## PGR2 snapshot result

The candidate completed one initial and one reuse run per adapter using the
same 60-second PGR2 snapshot procedure. Both reuse runs had zero SPIR-V misses.
The initial labels describe run order; previously populated shader-profile
data meant they were not pure cold-cache runs.

The retained previous-main reference is the published three-run warm median
for the same NVIDIA Vulkan snapshot procedure. It uses executable
`5c27d5310add91901f5a132c38d250492abf3d5eed253c2e6fe8cf63fb764768`; the
control was not rebuilt. Positive Improvement % is favorable. FPS is
`+good`; interval metrics are `+bad`.

| Metric | Raw + | Previous main NVIDIA | PR76 NVIDIA reuse | Improvement % | Result |
| --- | --- | ---: | ---: | ---: | --- |
| FPS | `+good` | 29.408 | 29.384 | -0.080% | Neutral central metric |
| Mean interval | `+bad` | 33.992 ms | 34.004 ms | -0.035% | Neutral central metric |
| p95 interval | `+bad` | 39.714 ms | 39.718 ms | -0.010% | Neutral central metric |
| p99 interval | `+bad` | 43.144 ms | 42.989 ms | +0.359% | Neutral central metric |
| Maximum interval | `+bad` | 52.959 ms | 58.480 ms | -10.425% | Adverse single-run maximum |

The NVIDIA reuse run recorded no intervals at or above 75 ms. Its 58.480 ms
maximum is 1.545% above the largest maximum in the three retained previous-main
runs (57.590 ms). This single candidate run does not establish a same-GPU tail
regression or a performance benefit. Its average, p95, and p99 remain close to
the previous-main medians.

The AMD run is a compatibility and adapter comparison, not an isolation of
host-copy cost. It combines a different Vulkan device and driver with the
cross-GPU host-copy transport. Relative to the candidate NVIDIA reuse run:

| Metric | Raw + | NVIDIA shared reuse | AMD host-copy reuse | Improvement % |
| --- | --- | ---: | ---: | ---: |
| FPS | `+good` | 29.384 | 25.415 | -13.510% |
| Mean interval | `+bad` | 34.004 ms | 39.346 ms | -15.711% |
| p95 interval | `+bad` | 39.718 ms | 47.374 ms | -19.276% |
| p99 interval | `+bad` | 42.989 ms | 55.764 ms | -29.717% |
| Maximum interval | `+bad` | 58.480 ms | 100.149 ms | -71.253% |

The AMD host-copy path rendered correctly and completed the measurement, but
it was slower on this dual-GPU test system. The NVIDIA adapter remains involved
because its OpenGL context presents the window. These results support AMD as a
working compatibility/offload choice; they do not support calling it the
faster option on this host.

## Qualification status

| Workload | Path | Status | Remaining decision |
| --- | --- | --- | --- |
| Focused startup | AMD Vulkan / NVIDIA GL host copy | PASS | Black-screen correction reproduced and fixed |
| Focused startup | NVIDIA Vulkan / NVIDIA GL shared | PASS | Same-GPU control retained |
| PGR2 snapshot | NVIDIA shared | COMPLETE | Central metrics neutral; one-run maximum needs full-suite context |
| PGR2 snapshot | AMD host copy | COMPLETE | Functional, measurably slower adapter/path combination |
| Full XISO suite | NVIDIA shared and AMD host copy | PENDING | Correctness and broad performance gate |
| PGR2 full start | NVIDIA shared and AMD host copy | PENDING | Retail performance gate |
| Morrowind snapshot | NVIDIA shared and AMD host copy | PENDING | Retail performance gate |

## Evidence

- `manifest.json` records source, build, toolchain, test identity, and remaining
  gates.
- `build-receipt.json` records verified build options, focused unit status, and
  artifact hashes.
- `focused-runs.csv` contains the two sanitized native run rows.
- `focused/amd-gpu-info.json` and `focused/nvidia-gpu-info.json` are the atomic
  request-versus-actual adapter and presentation records.
- `pgr2-snapshot-runs.csv` records all four candidate snapshot runs, adapter
  identities, presentation paths, guest and host frame metrics, and SPIR-V
  cache outcomes.
- `pgr2-snapshot-comparisons.csv` records the positive-good calculations
  against retained previous main and between candidate adapters.

The first native wrapper result correctly rendered AMD output and produced the
right GPU record, but the wrapper checked a nonexistent `status` property
instead of schema field `state`. That checker failure is excluded from the
table. The corrected wrapper reran both focused cells once and both passed.
