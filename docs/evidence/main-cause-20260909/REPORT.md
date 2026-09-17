# Main-based Morrowind cause counters

**Outcome: useful Vulkan attribution; OpenGL snapshot load failed. No
optimization or performance gain is qualified by this diagnostic build.**
The same DSP assertion also occurred in a readiness-only control using the
retained, uninstrumented baseline executable. No baseline was rebuilt.

## Identities and completed work

| Item | Identity / result |
| --- | --- |
| Baseline | `Mainkill1/xemu` main `586de4f32c11001c0abe072c3530236f1571b372` |
| Tested baseline behavior | `390a00e694fe8f3fb35459c91dc87913d0973abd`; application/build files identical to main |
| Baseline executable SHA-256 | `70b3a1236f770d52b62c363b59cc19b747797037a12941da23bbfbd32b5fac00` |
| Probe | Main plus [diagnostic.patch](diagnostic.patch); tree `a36757d638bcb19e752ca885b7fe78889979dd6c` |
| Probe executable SHA-256 | `1fc1ecd61be95b4caf6602440242a3b32c3789c95063f507c073019c4c18281e` |
| Build | Windows cross-build passed; O2, LTO, symbols, assertions and QOM cast checks retained |
| Vulkan | One 20-second cell completed; 56 cumulative counter records retained |
| OpenGL | Failed before snapshot readiness; no gameplay measurement |
| Baseline control | One OpenGL readiness attempt reproduced the same DSP assertion |
| Cleanup | No remaining owned emulator or private HDD; snapshot seed unchanged |
| Offline analysis | Seven analyzer tests passed; regenerated deltas match the original analysis |

The [manifest](manifest.json) pins toolchain, hardware, settings, input recipe,
snapshot hash, source and binary identities. Hardware was Windows 10 Pro,
Ryzen 9 6900HX, with an RTX 3070 Ti Laptop GPU and integrated Radeon adapter.
The manifest records both installed driver versions; it does not infer adapter
selection from their presence. CPU/GPU utilization, power and memory telemetry
were not collected in this probe.

The workload restores an outdoor Morrowind snapshot, waits for QMP running,
waits five seconds, presses Start, waits two seconds, presses B, waits two
seconds, then measures for twenty seconds. Effective presentation interval was
one, without an explicit override. Game files, snapshots, system ROMs and
private machine configuration are not distributed in this evidence package.

## What the counters establish

The analyzer selects samples inside the recorded UTC window, then differences
cumulative counters per host thread. Rates use each thread's monotonic elapsed
time between its first and last included samples. Those spans are 19.430 seconds
for the graphics thread and 19.002 seconds for the vCPU, not the entire requested
20-second window. It does not interpolate missing endpoint samples.

| Route | Observed work | Bounded next investigation |
| --- | --- | --- |
| Dirty-memory tracking on graphics thread | 6,746 reset calls/s; 25.28 million scanned TLB entries/s; 6,274 newly armed entries/s; 17.27% of scans armed no new entry | Attribute range/page generations before changing rearming. A dirty precheck alone can race with guest writes. |
| Helper TB lookup | 10.39 million calls/s; 93.20% direct-cache hits; 706,558 secondary table hits/s; 83.90% of misses first fail the PC check | Compare retained cache/hash experiments and distinguish collision cost from dispatch frequency. |
| Main-loop TB lookup | 99.876% direct-cache hits | Explain the high loop-exit count and low linking count before proposing a dispatch change. |
| Same-page invalidation | 555 invalidated TBs/s, but zero current-TB encounters and zero forced SMC restarts | Lower priority for this captured scene; this does not disprove the pathology in other workloads. |

Full per-thread totals, rates and derived values are in
[vulkan-summary.json](vulkan-summary.json). This measures repeated work under
instrumentation, not its individual CPU cost or a promised FPS percentage.
Main already has empty-MMU-mode skipping and static-state helper lookup; neither
is a missing optimization against this baseline. Audio remained uninstrumented.

Each thread owns its counters; output is amortized to at most once per second.
TLS increments, clock checks and output can affect scheduling. The probe's
16.607 display-write intervals/s, 150.610 ms p95 and 168.983 ms p99 are retained
in [vulkan-run.json](vulkan-run.json) **only as diagnostic context**. The metric
counts guest display writes, not rendered or displayed FPS. No comparison to
uninstrumented baseline throughput is valid.

The final Vulkan image was manually inspected for the expected outdoor scene.
Automated nonblack checks passed. Neither check establishes pixel-perfect
correctness or qualifies every intermediate frame. Its hash is recorded; game
images are not needed to reproduce the counter arithmetic.

## OpenGL failure and existing repair

Both the probe and retained baseline emitted:

```text
read_memory_p: assertion failed: ((r & 0xFF000000) == 0)
```

This is the DSP program-word check in
`hw/xbox/mcpx/apu/dsp/interp/dsp_cpu.c:893`. See the sanitized
[failure excerpts](load-failures.json), [failed cell](opengl-run.json), and
[baseline control receipt](baseline-load-control.json). The control ran no
performance window. The old controller expected a process named `xemu` while
the existing baseline was named `xemu-dwarf`; independent process/exclusive-disk
checks completed cleanup after that naming mismatch. The assertion was emitted
by the exact baseline bytes, independently of the controller timeout.

Main's `mcpx_apu_pre_load()` resets under the APU lock but does not explicitly
quiesce the frame thread through the following VMState restore. Later source
contains that quiescence and releases the BQL while waiting, preserving the
established IRQ lock order. This repair is already discussed in
[xemu #38](https://github.com/Mainkill1/xemu/issues/38#issuecomment-5598086580)
and carried by the broader proposals #51/#52. Its absence from main is not a
newly discovered, entirely untracked omission. The separate
[main-only candidate report](../main-apu-load-20260909/REPORT.md) records passing
snapshot cells on both renderers; the failed baseline/probe records here remain
unchanged.

## Reuse existing baseline evidence

[Source equivalence](baseline-source-equivalence.json) lists every change from
the tested baseline behavior to pinned main: README plus seven evidence CSVs.
[Six retained runs](baseline-run-index.json) match the baseline binary identity:
three passing and **one failing** Vulkan full suite, plus two passing PFIFO
targeted runs. The failed suite reports `report_query.clear_boundary='FAIL'`
despite passing functional-hash comparison and zero VUIDs. It remains failed.

[Per-run measurement exports](baseline-runs/) retain all reported test rows,
including structural group rows, unfavorable timings and original summary
hashes. Machine paths/environment are omitted; these JSON files are sanitized
exports, not byte-identical originals. No additional historical run was executed.
Matching OpenGL and retail percentile records for this exact baseline have not
yet been located; PR #52's different source cannot fill that gap.

The retained baseline catalog has 142 executable leaves plus five groups.
The [published v2 XISO](../../../releases/eng523-report-query-oracles-v2.json)
has 144 leaves plus five groups. Current source additionally contains newer
opt-in workloads. These are separate source/catalog/image contracts: never
compare their full-suite totals as identical work. This counter investigation
does not change guest tests or produce a new XISO. Any subsequent suite build
must publish its own source, catalog, image hash and results.

## Reproduce the offline analysis

From the test repository root:

```sh
python3 -m unittest discover -s tests -p test_cause_counters.py
python3 utils/analyze_cause_counters.py \
  docs/evidence/main-cause-20260909/vulkan-counters.jsonl \
  --start-utc-us 1788944048137590 --end-utc-us 1788944068146436 \
  --output counter-summary.json
```

The [56 counter records](vulkan-counters.jsonl) preserve complete emitted
counter objects, including warmup/cooldown rows that the analyzer excludes.
The analyzer rejects missing samples, counter resets, schema changes, reversed
clocks and incomplete lookup accounting. Source reproduction uses the pinned
main commit plus `git apply --index diagnostic.patch`; `git write-tree` must
match the manifest before building. The patch is temporary instrumentation,
not a proposed production optimization.
