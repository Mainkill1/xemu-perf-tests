# PVIDEO overlay workload

These revision-2 xemu-only leaves generate YUY2 input and program the public NV2A PVIDEO
MMIO registers. They exercise display uploads and compositing on OpenGL and
Vulkan, including Vulkan image/view/sampler reuse investigated in
[Mainkill1/xemu #263](https://github.com/Mainkill1/xemu/issues/263).
Physical Xbox behavior is unqualified; the suite is registered only when
`enable_xemu_only_tests` is true.

| Stable leaf ID | Legacy result | Fixed work at multiplier 1, warmups 0 |
|---|---|---|
| `pvideo.steady_upload` | `Pvideo::SteadyUpload` | Eight samples of 128 vblank-paced guest frame submissions; 128×128 overlay, source bytes inverted every 64 frames, source address switched every 128 frames |
| `pvideo.resize_toggle` | `Pvideo::ResizeToggle` | Same frame count; repeats the eight phases below twice |

Both use a 68 KiB contiguous uncached allocation below 64 MiB. Two source
windows start at offsets 0 and 32,768. A final allocated 4 KiB guard page
keeps the one-past source end below the inclusive LIMIT: both xemu renderer
decoders currently compare `offset + pitch * height <= LIMIT`. No guard bytes
are read, and no renderer limit interpretation is changed. Before profiling, the fixture selects the render front buffer: the common
suite progress screen uses a separate debug buffer that cannot exercise
GPU PVIDEO compositing. Each frame clears the guest buffer to
ARGB `0xff334c99`, programs PVIDEO at guest pixel (256,176), and finishes a
pbkit buffer swap. Source YUY2 has neutral chroma (128) and luma 16/235 in four
checker quadrants. Every source generation is complete before its MMIO write.

## Resize/toggle phases

Each phase lasts 64 frames. Even phases use the normal checker; odd phases
invert it. Repeat after frame 511.

| Phase | Size | Source offset | Overlay |
|---:|---:|---:|---|
| 0 | 128×128 | 0 | on |
| 1 | 128×128 | 0 | on, changed bytes at the same address |
| 2 | 128×128 | 32,768 | on, changed source address |
| 3 | 64×64 | 32,768 | on, changed size |
| 4 | 128×128 | 0 | on, restored size |
| 5 | 128×128 | 0 | on, changed bytes |
| 6 | 128×128 | 0 | off |
| 7 | 128×128 | 32,768 | on again |

## Correctness and limits

Before timing, four source known answers check both sizes and inversions.
Their FNV-1a64 values are pinned from an independent quadrant construction;
the host contract also checks a literal 4×2 YUY2 byte vector. The final source
hash is checked outside timing and emitted as `metadata.source_kat` with
`source_oracle_pass=true`.

**The guest framebuffer hash excludes the PVIDEO overlay.** A guest PASS or
matching source hash therefore cannot qualify host compositing. A native
campaign must retain independent host screenshots during normal/inverted,
address switch, resize, disabled and re-enabled phases. Check orientation,
bounds, unchanged background and absence of stale pixels. Match captures to
the presented phase; reject incomplete coverage. On Vulkan, a separate
instrumented diagnostic run can use the existing `XEMU_VK_PERF_LOG` records
and their `pvideo_upload` caller to establish that the upload path was used.
This diagnostic run must be separate from performance measurements.

Timing includes guest source changes, background clears, MMIO and buffer
swaps, plus the selected profile completion policy. Each sample means
128 guest frame submissions, not one upload or one frame. The final swap
can still await scanout at the measurement boundary; host presentations are
not counted by this guest result. pbkit waits for vblank; throughput
can be limited by guest refresh. Guest time alone cannot establish a host
CPU saving or predict game FPS. Use host CPU/GPU measurements per observed host frame, matched settings/binaries and repeated ABBA/BAAB processes. Preserve
all raw samples and failed attempts.

Profiles under `resources/pvideo-*.json` use eight samples, no warmups,
multiplier 1 and per-iteration completion (after each 128-frame batch).
Increased multipliers/warmups add whole frame batches and must be recorded.
The descriptor timeout is 120 seconds per leaf to allow slower emulation of
this vblank-paced work; it is not a performance acceptance threshold.

## Build and verification

Use the pinned NXDK revision and normal Release XISO target. Run:

```sh
python3 utils/test_catalog.py --check
python3 -m unittest discover -s tests -p 'test_*contract.py'
cmake --build BUILD --target xemu-perf-tests_xiso
```

Register the actual built ISO/catalog with the maintained Xemu-Test-Runner
XISO workflow and a clean prepared FATX seed. Native overlay correctness,
OpenGL/Vulkan, 1x/4x and full-suite validation remain required before merging
this fixture. Emulator performance evidence belongs in the owning xemu PR;
this repository retains the workload and its contracts.
