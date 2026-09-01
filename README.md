xemu-perf-tests
====

Deterministic Xbox workloads for finding xemu correctness and performance
changes. Fixed work, checksums, known-answer values, and framebuffer hashes
prevent a faster result from silently hiding changed output.

## Choose your goal

| Goal | Start here |
| --- | --- |
| Run the full XISO in xemu | [Automated xemu run](#automated-xemu-run) |
| Run from the on-disc Xbox menu | [Operator guide](docs/running-tests.md#manual-xemu) |
| Collect physical-Xbox evidence | [Physical Xbox workflow](docs/running-tests.md#physical-xbox) |
| Compare output hashes | [A/B correctness](#ab-correctness) |
| Understand or extend a test | [Generated catalog](docs/generated/test-catalog.md) and [adding tests](docs/adding-tests.md) |
| Diagnose a failed stable ID | [Generated failure guide](docs/generated/test-failure-guide.md) |

## Current package

Use `xemu-perf-tests-eng473-final-1f5fb0d.iso`.

| Identity | Value |
| --- | --- |
| XISO SHA-256 | `04251d83f66afecb74fff19a8efcc4b6587fc17e8202e0f2031df65d4da54a55` |
| Guest source | `1f5fb0db59a68c55cbd4a3751d2540bca433b6c6` |
| Catalog | 136 executable leaves + 5 structural groups = 141 full-suite records |
| Release contract | [`releases/eng473-final-v1.json`](releases/eng473-final-v1.json) |

Download published artifacts from the
[`xemu-perf-tests` releases](http://10.0.4.4:3000/main/xemu-perf-tests/releases)
and verify the digest. Source is Forgejo commit
[`1f5fb0db59a6`](http://10.0.4.4:3000/main/xemu-perf-tests/commit/1f5fb0db59a68c55cbd4a3751d2540bca433b6c6).

## System flow

```text
catalog + fixed workload + selected plan
                  |
                  v
             Xbox XISO
          /                 \
manual persistent HDD       automated disposable HDD
E:\xemu_perf_tests          C:\xemu-lab\suite\work\test.img
archives current result     reformatted before each internal run
          |                          |
          v                          v
byte-exact results/history   timestamped host run directory
                             byte-exact + normalized evidence
          \                          /
           +-- correctness, then timing --+
```

The XISO never formats a manual HDD. It manages only its configured output
directory. The internal lab runner formats only its dedicated disposable
`work\test.img`; its FATX history is temporary. Public-safe automation must
create a new per-run image and refuse every existing or user-provided HDD.

## Automated xemu run

The verified lab runner is `C:\xemu-lab\suite\run-suite.py`. Run one xemu
process. This exact command selects every current guest test:

```bat
C:\xemu-lab\suite\python313\python.exe C:\xemu-lab\suite\run-suite.py ^
  --mode perf --full-suite ^
  --xemu C:\path\to\xemu.exe ^
  --guest-iso C:\path\to\xemu-perf-tests-eng473-final-1f5fb0d.iso ^
  --backend vulkan --scale 1 ^
  --completion-mode per_iteration --expected-record-count 141
```

Use `--backend opengl` for OpenGL. Add `--vulkan-validation` only to a Vulkan
correctness run; diagnostic/validation timing is not performance evidence.
Unmodified upstream xemu without lab live markers may add
`--allow-missing-live-markers --host-telemetry off`. That waives timing
attribution only; record count, checks, hashes, and validation remain required.

## Retrieve results

Manual/physical-Xbox results use the persistent HDD:

```text
E:\xemu_perf_tests\results.txt
E:\xemu_perf_tests\resolved-plan-result.json
E:\xemu_perf_tests\history\results-YYYYMMDD-HHMMSS[-N].txt
```

Automation extracts the temporary FATX result into its timestamped host run
directory. That host directory—not `work\test.img`—is the retained record. It
contains byte-exact `results.txt`, `guest-config.json`,
`normalized-results.json`, xemu/XISO identity, xemu log, backend, scale,
completion mode, host identity, and available validation evidence. Copy; never
edit or re-save `results.txt`. Detailed safe-copy rules are in the
[operator guide](docs/running-tests.md#result-locations-and-safe-copy).

## Read the verdict

| Verdict | Meaning |
| --- | --- |
| PASS | Required records closed and checks passed |
| FAIL | At least one required check or soft assertion failed |
| PARTIAL | Only closed records recovered; never qualification evidence |
| Crash/assert/device loss/hang | Incomplete emulator or infrastructure run |
| Missing oracle | Execution may be valid; correctness remains unverified |

A soft failure may continue to later tests, but its leaf and final run remain
FAIL. A group reports child completion, never independent timing. A prior xemu
framebuffer hash is a regression oracle, not retail-Xbox truth.

## A/B correctness

Use one XISO, config, renderer, scale, completion policy, seed, and fixed-work
multiplier. Calibrate work on baseline only. Alternate process order and retain
every raw result.

```text
python utils/hash_compare.py BASELINE_RUN CANDIDATE_RUN --json-out comparison.json
```

`1` means match, `0` mismatch, and `-` no baseline oracle. Missing/extra
records, zero eligible checks, or any mismatch return nonzero. Timing is usable
only after correctness passes. Batch tiny work into seconds-long samples; never
compare nanosecond-scale noise or separately calibrated candidate work.

## Troubleshooting

| Symptom | First action |
| --- | --- |
| Wrong tests run | Remove stale `E:\xemu_perf_tests\xemu_perf_tests_config.json`; E: overrides D: |
| Apparent hang | Record the final `RUNNING:` footer and host heartbeat before terminating |
| Soft red failure | Preserve result; releasing A advances but does not convert it to PASS |
| Missing/extra record | Check XISO identity, selection, expected count, and last closed record |
| Hash/KAT mismatch | Look up the stable ID in the [failure guide](docs/generated/test-failure-guide.md) |
| Upstream lacks live markers | Use the narrow compatibility flag above; do not claim timing attribution |
| Need full operating steps | Read [`docs/running-tests.md`](docs/running-tests.md) |

## Documentation and release evidence

- [Test architecture and layout](docs/test-system.md)
- [Operator workflows](docs/running-tests.md)
- [Generated catalog](docs/generated/test-catalog.md)
- [Add or extend a test](docs/adding-tests.md)
- [Machine-readable catalog](resources/catalog.json)
- [Resolved smoke-plan example](resources/plans/smoke.json)

### ENG473 final suite validation

The exact current XISO completed the 141-record OpenGL 1x full suite on the
dedicated Windows rig with both the upstream baseline and PR #2-#9 release
build. Both runs returned `PASSED` with no assertion, crash, hang, or device
loss.

| Check | Result |
| --- | ---: |
| Baseline records | 141/141 |
| PR #2-#9 records | 141/141 |
| Comparable framebuffer/work/result hashes | 245/245 match |
| Hash mismatches | 0 |
| Missing or extra records | 0 |

Two same-address queued-texture framebuffer observations are excluded from
pixel comparison because the guest overwrites unified texture memory without a
GPU synchronization boundary. Their work and result hashes remain mandatory.
Synchronized same-address and distinct-address ring routes remain strict pixel
oracles. Exact identities and run paths are in
[`releases/eng473-final-v1.json`](releases/eng473-final-v1.json).

### Prior complete performance campaign

The final compatible campaign exercised this 141-record workload contract
against upstream `d73326b6` and candidate `2ae71e6c` (published equivalent tree
through pull #10 plus ENG-465). The dedicated Windows rig used 1x, VSync off,
three guest warmups, multiplier four, and per-iteration completion.

| Backend | Candidate records | Semantic differences | Fresh-process image checks | Fixed-work throughput |
| --- | ---: | ---: | ---: | ---: |
| OpenGL | 141/141 | 0 | 55/55 match | +3.87% |
| Vulkan | 141/141 | 0 | 55/55 match | +6.61% |

All 55 full-run image differences matched when rerun one target per fresh
process, identifying order-dependent guest state rather than an accepted render
difference. Upstream Vulkan lost the device on two bordered BC2 routes; the
candidate completed them. Seven stale pixel KAT expectations are exact,
XISO-hash-bound limitations after both builds produced the same values and
their independent framebuffer oracles passed.

Strict evidence is in
[`xemu-perf-lab` PR #5](http://10.0.4.4:3000/main/xemu-perf-lab/pulls/5).
These numbers describe the wider candidate, not the narrower PR #2-#9 package.
Matching release/diagnostic executables and identities are in
[`xemu-pr-train` releases](http://10.0.4.4:3000/main/xemu-pr-train/releases)
and [`releases/eng466-publication-v1.json`](releases/eng466-publication-v1.json).

### ENG462 integration history

ENG462 added PFIFO array elements, texture/sampler identity checks, Vulkan
submission-lifetime plans, RUNNING status, soft-failure screens, and the
141-record integration image. See
[`releases/eng462-integration-v1.json`](releases/eng462-integration-v1.json) and
[`releases/eng462-final-ab-20260830.md`](releases/eng462-final-ab-20260830.md).
Older release data below remains history, not the current download.

### Historical ENG458 texture validation

The 12-route S3TC/BC lifetime matrix, exact KATs, historical image identity,
and verified runner command moved to
[`docs/s3tc-validation.md`](docs/s3tc-validation.md). It remains evidence, not
the current download.

# Usage

Tests execute automatically after the source-defined three-second timeout when
no gamepad input is received.

Individual tests may be executed via the menu.

## Xbox on-disc interface

Booting the XISO opens a controller-driven interface before autorun. Any
controller input cancels the three-second autorun countdown.

The root screen identifies the catalog and active selection. The test workflow
uses these public entries:

1. `Run Suite`: run the full selection or open one suite and run its tests.
2. `Individual Tests`: browse stable IDs by subsystem, inspect contracts, and
   run mapped routes.
3. `Results`: browse the bundled reference, current result, and archives;
   inspect records, graphs, failures, and A/B comparisons.
4. `System Information`: refresh guest CPU, timer, RAM, drive, NV2A/MCP,
   CPU/board temperature, video, and kernel values.
5. `Plans`: run the full selection, quick smoke, S3TC/BC, or Vulkan-memory
   plans.
6. `Settings`: select single-run/result-saving or continuous/no-save behavior.
7. `About/Controls`: starts with `Mainkill1's Test Suite`, then shows catalog
   identity, result path, and controller actions.

The full unfiltered image exposes 136 leaf tests, five structural groups, and
141 exact legacy aliases. A catalog stage belonging to a grouped execution
route is still discoverable by its stable ID. Running that route can emit its
sibling stages because those stages share initialization and lifetime state;
use a resolved plan when an independently selectable stage mask is required.
Resolved-plan boots advertise only routes that plan can execute.

During `Run all`, the screen reports suite progress. On completion it shows
`PASS` or `FAIL`, emitted leaf/group counts, resolved-plan completeness,
oracle-failure count, the first failed stable ID, catalog identity, and the
saved result path. `reboot_or_shutdown_delay` controls the readable hold with
no hidden delay: use `0` for unattended hosts and at least `30000` for a
physical-console review. The sample physical-console config uses 30 seconds.

Results are saved to:

```text
E:\xemu_perf_tests\results.txt
E:\xemu_perf_tests\resolved-plan-result.json  (resolved plans only)
E:\xemu_perf_tests\history\results-YYYYMMDD-HHMMSS[-N].txt
```

On a persistent manual/physical-Xbox HDD, an existing `results.txt` is moved
into `history` before a new log opens. Files are never pruned by the XISO:
retention is an explicit storage decision and benchmark evidence is not
silently discarded. If preservation fails, the new run is refused instead of
overwriting the old result. Automated disposable images do not provide
persistent FATX history.
`-N` disambiguates archives created in the same clock second.

The UI reports execution/oracle status. A framebuffer hash from xemu is still
a regression oracle, not proof of retail-hardware correctness.

### 640x480 results inspector

The guest stays at the Xbox-native 640x480 logical framebuffer. Internal xemu
scaling enlarges rendered surfaces; it does not create more guest UI space.
The result browser spends that fixed screen on progressive detail:

1. `Results` lists a bundled completed OpenGL 1x reference, the current result,
   and timestamped archives. The bundled run is the default in-memory baseline.
2. Open a run, then `Graphs`, to see every timed record directly. Each opens on
   `TRACE`; X cycles `TRACE`, `HISTOGRAM`, and `SUMMARY`.
3. Press Y on any run to replace the in-memory A/B baseline.
4. Open a non-baseline run and select `Compare to selected baseline`. Matching
   stable IDs show aggregate values and a cyan-baseline/green-candidate trace
   when sample procedures match. Press X for regressions only.
5. The normal record list remains available. Press X there to switch between
   all records and failures only.

New timing records store average, minimum, maximum, median, nearest-rank p95,
MAD, sample count, unit, and direction. Trace rendering buckets samples by the
510-pixel plot width and retains each bucket's minimum/maximum envelope, so a
spike is not averaged out. The plot starts at X=90 and Y=205, leaving fixed
PBKit text rows for duration/count labels on the left and sample/value labels
below it. Left/Right selects a trace bucket or histogram bin; the bottom row
reports its sample range and values. Histogram bin count derives from the same
visible width with an eight-pixel minimum bar width. These values describe
display geometry, not benchmark behavior.

The run list streams summaries. Raw samples are rescanned only for the selected
record. A 512 KiB scratch budget bounds Xbox RAM use; larger records are
deterministically downsampled and marked approximate. This is a byte budget,
not an unexplained sample limit. Result-viewer allocations and drawing happen
only after opening saved results, never inside measured work.

Incomplete legacy JSON files recover only fully closed records and display
`PARTIAL - final totals unavailable`. The current writer still uses the legacy
JSON-array container, so an interrupted final record may be lost; an
append-record container and byte-offset sidecar remain future format work.
Framebuffer images are not stored, so the console can show hashes and failure
text but cannot reconstruct a visual difference. Baseline selection lasts for
the current application session and does not rename or mutate either run.
`D:\reference-results.txt` is a read-only, 141-record completed run captured on
2026-08-30 with OpenGL, 1x scale, xemu `d73326b62199`, three warmups,
multiplier four, and per-iteration completion. It is a performance/regression
reference, not a retail-Xbox correctness oracle. Full provenance is stored in
`D:\reference-results-provenance.txt`.

### Physical Xbox acceptance checklist

This branch has host contract and build gates; those do not substitute for a
real controller/display test. Before calling the UI hardware-validated:

1. Boot the release XISO on a retail Xbox with no config. Confirm catalog ID,
   `136 tests / 5 groups / 141 aliases`, countdown, and cancellation.
2. Open Results and inspect one run summary, graph, and record. Open System
   information, press A, and confirm RAM/drive values refresh. Visit About,
   every root suite, and every catalog suite. Hold Up/Down and use
   Left/Right at first, middle, and last pages; confirm no blank or stuck page.
3. Open entries from each catalog suite. Confirm stable ID, legacy alias,
   description, route, A-run help, and B/Back return.
4. Run one ordinary leaf, one grouped S3TC route, one complete suite, and Run
   All. Confirm progress remains readable and controller navigation recovers.
5. Inject one known oracle failure. Confirm FAIL, first stable ID, saved path,
   and 30-second hold. Repeat a passing plan and confirm PASS.
6. Copy `results.txt` from E:, verify JSON, record XISO/catalog hashes and
   console/video mode. Do not promote observations to hardware goldens until
   repeated Xbox runs agree.

# Controls

DPAD:

* Up - Move the menu cursor up. Inside a test, go to the previous test in the active suite.
* Down - Move the menu cursor down. Inside a test, go to the next test in the active suite.
* Left - Move the menu cursor up by half a page.
* Right - Move the menu cursor down by half a page.
* A - Enter a submenu or test. Inside a test, re-run the test.
* B - Go up one menu or leave a test. If pressed on the root menu, exit the application.
* X - Run all tests for the current suite.
* Y - Toggle between one shot and continuous test mode. In continuous mode, tests are designed to run near the edge of
  60 FPS on 1.0 Xbox devkit hardware, provided that the application is built in release mode and XBDM notifications are
  not attached.
* Start - Enter a submenu or test.
* Back - Go up one menu or leave a test. If pressed on the root menu, exit the application.
* Black - Exit the application.

LEFT THUMBSTICK:

* Up/down/left/right use the same menu routes and held-direction repeat as the
  D-pad.
* A direction engages at half stick travel and releases below quarter travel.
  The gap is intentional hysteresis: ordinary center drift cannot move the
  cursor and a held direction cannot chatter near one threshold.

# Test configuration

Behavior can optionally be determined via a JSON configuration file loaded from the XBOX.

```json
{
  "settings": {
    "disable_autorun": false,
    "enable_autorun_immediately": false,
    "enable_shutdown_on_completion": false,
    "skip_tests_by_default": false,
    "delay_milliseconds_between_tests": 0,
    "measurement_iterations_multiplier": 1,
    "output_directory_path": "e:/xemu_perf_tests"
  }
}
```

`measurement_iterations_multiplier` scales the fixed measured iteration count
of every selected test without changing its warmup count. A host runner can use
a short baseline-only calibration to choose enough fixed work for a sustained
15-30 second measurement, then reuse that exact multiplier for all baseline and
candidate runs. Valid values are 1 through 100000. Never calibrate the candidate
independently, because that would compare different amounts of guest work.

In the default release build, the program will look for this file in the `output_directory_path` (
`e:/xemu_perf_tests/xemu_perf_tests_config.json`) and `d:\xemu_perf_tests_config.json`, taking whichever is found
first.

When building from source, the `sample-config.json` file in the `resources` directory can be copied to
`resources/xemu_perf_tests_config.json` and modified in order to change the default behavior of the final xiso.

#### Filtering test suites/cases

New automation should use a host-resolved plan containing explicit stable leaf
IDs. The guest validates the bundled catalog ID, rejects duplicate, unknown, or
group IDs, derives the selected execution cases and composite stage masks, and
requires the emitted leaf set to match the plan. `selected_leaf_count` is
validated against the unique IDs instead of a fixed whole-suite record count.

```json
{
  "settings": {"enable_autorun_immediately": true},
  "resolved_plan": {
    "schema_version": 2,
    "plan_id": "sha256:...",
    "catalog_id": "sha256:...",
    "selected_leaf_count": 1,
    "tests": [{"id": "surface.cpu_read_clean_surface"}]
  }
}
```

`resources/catalog.json` and `docs/generated/test-catalog.md` are generated
from `utils/test_catalog.py`. Run `python3 utils/test_catalog.py --check` in CI.
The checked-in `resources/plans/smoke.json` is a complete example. Legacy
`test_suites`/`skipped` configuration remains supported as an adapter, but it
cannot be combined with a resolved plan.

Composite parents are group outcomes. They retain their legacy result record
shape during migration, with zero-valued compatibility timing fields and an
explicit `kind: group`; they never copy the final child's timing.

The `"test_suites"` section may be used to filter the set of tests.

For example, suppose the program contains four test suites: `Default suite`, `Unlisted suite`, `Skipped suite`, and
`Suite with skipped test`. Each test suite contains two tests, `TestOne` and `TestTwo`. Without any filtering, the menu
tree would be something like:

```
Run all and exit
Default suite
  TestOne
  TestTwo
Unlisted suite
  TestOne
  TestTwo
Skipped suite
  TestOne
  TestTwo
Suite with skipped test
  TestOne
  TestTwo
```

___Note___: The names used within `"test_suites"` and its children are the same as the names that appear in the
`xemu_perf_tests` menu.

By default, any descendant of the `"test_suites"` object that contains a `"skipped": true` will be omitted.

For example, the following config disables the named suite/test entries while
retaining unlisted entries:

```json
{
  "settings": {},
  "test_suites": {
    "Skipped suite": {
      "skipped": true,
      "TestOne": {}
    },
    "Suite with skipped test": {
      "TestTwo": {
        "skipped": true
      }
    },
    "Default suite": {
      "TestOne": {}
    }
  }
}
```

Resulting in

```
Run all and exit
Default suite
  TestOne
  TestTwo
Unlisted suite
  TestOne
  TestTwo
Suite with skipped test
  TestOne
```

This behavior may be modified via the `"skip_tests_by_default"` setting, allowing only entries with an explicit
`"skipped": false` to be retained. For example, the following config will disable all tests except the `TestOne` case
under `Default suite`.

```json
{
  "settings": {
    "skip_tests_by_default": true
  },
  "test_suites": {
    "Default suite": {
      "TestOne": {
        "skipped": false
      }
    }
  }
}
```

`GameLoadComposite` also provides `08-LongUnlockedScene`. It is one XBE test
case with ordered CPU, PFIFO, alpha/overdraw, streaming/surface-reuse,
combined, and full-system stages. Each stage has an independent guest marker
window while the normal test-case filter can select it by name:

```json
{
  "settings": { "skip_tests_by_default": true },
  "test_suites": {
    "GameLoadComposite": {
      "08-LongUnlockedScene": { "skipped": false }
    }
  }
}
```

Optional root `game_load_composite.long_unlocked_scene` settings keep the
global values as their backward-compatible defaults while allowing calibration
per retained stage. Stage mask bits are CPU=1, PFIFO=2, alpha/overdraw=4,
streaming/surface-reuse=8, combined=16, and full-system=32. `stages` is an
optional named-list filter intersected with `stage_mask`.

```json
{
  "game_load_composite": {
    "long_unlocked_scene": {
      "stage_mask": 63,
      "stages": { "cpu": true, "pfifo": true, "alpha_overdraw": true,
                  "streaming_surface_reuse": true, "combined": true, "full_system": true },
      "measurement_iterations_multiplier": { "cpu": 12, "pfifo": 4, "alpha_overdraw": 8 },
      "warmup_iterations": { "cpu": 1, "pfifo": 0 },
      "gpu_precondition": { "alpha_draws": 8192 }
    }
  }
}
```

Omitted stage multipliers/warmups inherit the global settings. The fixed,
untimed GPU precondition runs once immediately before the first retained GPU
stage; `alpha_draws: 0` disables it. Each retained stage writes a normal result
record with its applied warmup/multiplier and precondition metadata. The final
`GameLoadComposite::08-LongUnlockedScene` result is an intentionally extra
summary record (`kind: game_load_composite_long_scene_summary` and
`exclude_from_stage_window_mapping: true`); consumers must map F0/F1 windows
only to `kind: game_load_composite_long_scene_stage` records.

`GameLoadComposite` also provides `09-CrossTitleHotpath`. It keeps one
asset-free XBE busy with eleven fixed stress slices that match current title
discovery fronts: queued vertex CPU writes, PGR2-like small draws, texture
update reuse, surface reuse, pipeline-state churn, constant-blend-color
reuse, repeated unchanged texture-binding reuse, PGR2 inline-element pressure,
scaled surface pressure, S3TC texture rewrites with a wait after every draw,
and a matching GPU-wait control without texture or draw work.
The same XISO accepts a closed runtime job object and can run either a short
smoke or sustained fixed work without changing the known input/output contract.

Checked-in host configs can narrow that one test to a title-like shape. Current
PGR2 lag representation is `suite/configs/cross-title-pgr2-lag-representative.json`,
which selects small draws + texture reuse + surface reuse + pipeline churn +
blend-constant reuse + repeated unchanged texture-binding reuse.

```json
{
  "settings": { "skip_tests_by_default": true },
  "test_suites": {
    "GameLoadComposite": {
      "09-CrossTitleHotpath": { "skipped": false }
    }
  },
  "game_load_composite": {
    "cross_title_hotpath": {
      "fast_smoke": false,
      "stage_mask": 127,
      "stages": {
        "queued_vertex_cpu_writes": true,
        "pgr2_small_draws": true,
        "texture_update_reuse": true,
        "surface_reuse": true,
        "pipeline_state_churn": true,
        "blend_constant_reuse": true,
        "texture_binding_reuse": true
      }
    }
  }
}
```

The final `GameLoadComposite::09-CrossTitleHotpath` record is the summary.
Longer sustained runs are the evidence path. Short runs stay for smoke only,
because small windows can hide stalls and give defunct numbers.

Cross-title bit 512 is reported as `s3tc_streaming_fenced_draws`. The legacy
job key `s3tc_streaming_burst` remains accepted, but output never uses that
ambiguous name. Each sustained invocation performs 384 DXT1/DXT3/DXT5 guest
texture rewrites and draws, plus 385 declared `gpu_waits`: one after every draw
to protect the reused guest address and one final measured completion wait.
This is a synchronization-interaction workload, not a decode-only benchmark.
Fixed source and recipe KATs detect input corruption. Smoke mode uses 48 draws
and 49 waits with the same 1:1:1 format ratio.

Cross-title bit 1024 is `gpu_wait_control`. It performs 384 iterations of one
known PGRAPH pattern write, one `WaitForGpu`, and one exact register readback;
smoke mode performs 48. Its `pfifo_methods`, `fence_reads`, and `gpu_waits`
metadata are equal by construction. Comparing this stage with the S3TC stage
measures an idle-control floor only. It cannot exclude wait, fence, or lock
cost that appears only while draws keep the GPU busy. `gpu_waits` counts API
calls; it does not claim a fixed number of MMIO polls inside each call.

`GameLoadComposite::10-S3tcSyncFactor` is the 12-route ENG458 texture control
described at the top of this README. Each cell retains 16 visible tiles and
reports exact writes, bytes, generations, addresses, binds, waits, draws, and
vertex bytes. The cells are seconds-scale guest workloads, not nanosecond
microbenchmarks.

ENG379 supersedes ENG367's overwrite-only framebuffer oracle. Each of the 16
draws now targets one disjoint tile in a 4x4 grid and uses one unique RGB565
color with opaque alpha. The final framebuffer therefore preserves every
sampled texture update. Compile-time assertions require 16 tiles, 64 vertices,
unique colors, and an in-bounds grid; metadata reports `visible_tiles=16`,
`unique_colors=16`, and `overwrite_only_oracle=false` for changing-payload
routes. The dirty-once route uses one fixed source color across all 16
tiles (`texture_writes=2`, `texture_binds=17`, `payload_generations=1`,
`no_write_redraws=16`, `unique_colors=1`) and has its own fixed tile/result
KATs. ENG367 timing is diagnostic only until this tiled oracle passes on the
same builds.

`PFIFOArrayElements` adds three independently selectable, generated packet
capsules in the same XISO: `pfifo.array-element16` uses the Morrowind-shaped
38-word non-incrementing 16-bit payload, `pfifo.array-element32` renders the
equivalent 76-index geometry through a 76-word 32-bit payload, and
`pfifo.array-element-pgr2` uses the PGR2-shaped 29-word 16-bit payload. Each
has literal input/payload, rendered-pixel, final-state, and framebuffer hashes;
all are marked `REGRESSION_ONLY` until retail-Xbox corroboration. Smoke,
roughly 2-second/8-second quick, and 5-second/20-second sustained starting
configs are in `resources/pfifo-array-elements-*.json`. Duration claims require
baseline calibration and an identical fixed multiplier for both builds; short
runs are correctness/path checks only. See
[`docs/pfifo-array-element-workloads.md`](docs/pfifo-array-element-workloads.md).

The tile oracle is nonfatal. Every cell records `oracle_status`, failure count,
failure mask, reason, provenance, and compatibility key before the suite moves
on. A mismatch is still a failed oracle; it no longer becomes an assertion
screen that discards all later stability records. Host tooling decides whether
that exact failure has an explicit source/backend/scale compatibility allowance.

`PipelineTextureSwitch` adds `pipeline.texture-switch`, which alternates two
generated same-format texture backings plus address and sampler state over 512
fixed textured quads per invocation, and
`pipeline.shader-negative-control`, which holds those texture states fixed
while alternating shader combiner state. A third exact phase,
`pipeline.clear-texture-normal`, alternates a clear pipeline, a texture-only
change into a zero-binding normal inline draw, then a safe texture-only normal
draw. It requires a nonzero clear-binding dirty count, rejects attributing that
boundary as a texture-only bypass, and requires a later safe bypass. All phases
include `pipeline.sampler-only-identity`, which holds one five-level swizzled
image and its storage bytes fixed while alternating LOD clamps, filtering,
wrap modes, and border colors. Its host-counter gate expects cold setup to
create one image and two samplers; the warmed F0/F1 interval must reuse both
with no cache misses. Stable catalog IDs use the
`pipeline_texture_switch.*` namespace. All phases
provide exact input, backing, rendered-pixel, terminal-state, operation-count,
and framebuffer contracts with live failure/progress events. Smoke, initial roughly
2-second/8-second quick, and 5-second/20-second formal configs are in
`resources/pipeline-texture-switch-*.json`; dedicated third-phase configs are
in `resources/pipeline-clear-texture-normal-*.json`. Dedicated sampler-only
plans are in `resources/pipeline-sampler-only-identity-*.json`. Duration claims still
require control-only calibration and identical fixed work. See
[`docs/pipeline-texture-switch-workload.md`](docs/pipeline-texture-switch-workload.md).

Framebuffer provenance remains mandatory. Emulator-produced hashes are
regression oracles, not proof of retail Xbox correctness. Promote an oracle to
`RETAIL_XBOX` only after independent hardware runs of the exact XISO/job agree.

The catalog-bound `resources/vulkan-submission-lifetimes-*.json` plans combine
eleven existing deterministic leaves into an isolated validation matrix for
Vulkan resource pinning, eviction, vertex-read lifetime, fences, report
retirement, and teardown. Host counter and p95 gates are documented in
[`docs/vulkan-submission-lifetime-plan.md`](docs/vulkan-submission-lifetime-plan.md).

### Vulkan memory-pressure workload

`SurfaceRendering::XemuVulkanMemoryPressureRepresentative` and `Stress` are
deterministic, asset-free guest memory-pressure variants. Both use seed
`0x564D5052`, four fixed checkpoint samples, four fixed churn cycles per
sample, and the same address/format/resize recipe. Representative has guest
pressure multiplier 1 and 16 surface/texture identities; Stress has multiplier
4 and 64 identities. Stress performs 4,096 fixed churn bodies plus 64
no-new-key idle reuses before its oracle and is intended to produce a sustained
seconds-long host-memory window under Vulkan.

The guest pressure names do not encode Xemu's internal render scale. For a
render-scale comparison, run the same selected guest test externally once at
Xemu scale 1 and once at Xemu scale 4; do not compare Representative at one
scale with Stress at another. Results report `guest_pressure_multiplier`,
`guest_identity_count`, and `xemu_render_scale: "external"` so runner-captured
scale configuration remains the authority.

Each selected case emits five separately marked and recorded checkpoints:
`growth`, `plateau`, `alias_resize`, `reuse`, and `idle_retention`. Their result
metadata includes the fixed seed, guest pressure multiplier, guest identity
count, number of newly introduced keys, alias offset, transition count, and
`expected_memory_behavior`. Host
VRAM/RSS captures should grow in `growth`; stay flat during `plateau` and
`reuse`; may retain allocations after `alias_resize`; and remain observable
without new keys in `idle_retention`. Continued growth after completed
plateau/reuse/idle windows is the leak signal; stable elevated memory after
alias/idle is cache retention.

Copy [`resources/vulkan-memory-pressure-config.json`](resources/vulkan-memory-pressure-config.json)
to `xemu_perf_tests_config.json` to run only the sustained Stress recipe. It uses
per-iteration completion and zero warmups so every checkpoint has a clean host
telemetry boundary. The final four-tile framebuffer KAT is nonfatal: failures
emit `FAIL` events and are recorded as `oracle_status: FAIL`, but the test
continues to write its summary record.

# Building

## Prerequisites

This project uses https://pypi.org/project/nv2a-vsh to build vertex shaders. It may be
installed by running `pip install -r requirements.txt` from this directory.

## CLion

### Building

Under Settings > Build, Execution, Deployment > CMake

- Provide the path to the nxdk toolchain file under CMake Options

  `-DCMAKE_TOOLCHAIN_FILE=$CMakeProjectDir$/third_party/nxdk/share/toolchain-nxdk.cmake`

- Set the `NXDK_DIR` environment variable to the absolute path of the `third_party/nxdk` subdirectory.

- Optionally modify the `PATH` variable to make sure the path to your chosen version of Clang comes first.

### Debugging

#### Using [xemu](https://xemu.app/)

1. Create a new `Embedded GDB Server` target
1. Set the Target to the `<your project name>_xiso` target
1. Set the Executable to the `<your project name>` binary (it should be the only thing in the dropdown)
1. Set `Upload executable` to `Never`
1. Set `'target remote' args` to `127.0.0.1:1234`
1. Set `GDB Server` to the path to the xemu binary
1. Set `GDB Server args` to
   `-s -S -dvd_path "$CMakeCurrentBuildDir$/xiso/xemu-perf-tests_xiso/xemu-perf-tests_xiso.iso"` (the `-S` is
   optional and will cause xemu to wait for the debugger to connnect)
1. Under `Advanced GDB Server Options`
1. Set "Working directory" to `$ProjectFileDir$`
1. On macOS, set "Environment variables"
   to
   `DYLD_FALLBACK_LIBRARY_PATH=/<the full path to your xemu.app bundle>/Contents/Libraries/<the architecture for your platform, e.g., arm64>`
1. Set "Reset command" to `Never`

#### Using [xbdm_gdb_bridge](https://github.com/abaire/xbdm_gdb_bridge) and a devkit/XBDM-enabled Xbox

1. Create a new `Embedded GDB Server` target
1. Set the Target to the `<your project name>_xiso` target
1. Set the Executable to the `<your project name>` binary (it should be the only thing in the dropdown)
1. Set `Upload executable` to `Never`
1. Set `'target remote' args` to `127.0.0.1:1999`
1. Set `GDB Server` to the path to the xbdm_gdb_bridge binary (e.g., `<some_path>/xbdm_gdb_bridge`)
1. Set `GDB Server args` to `<your_xbox_ip> -v3 -s -- gdb :1999 e:\$CMakeCurrentTargetName$`
1. Under `Advanced GDB Server Options`, set `Reset command` to `Never`

To perform automatic deployment after builds:

1. Under the `Before launch` section, click the `+` button and add a new `Run external tool` entry.
1. Set the `Description` field to something like `Sync program and resources to the XBOX`
1. Set the `Program` field to the path to the xbdm_gdb_bridge binary (same as above)
1. Set `Arguments` to
   `<your_xbox_ip> -- mkdir e:\$CMakeCurrentTargetName$ && %syncdir $CMakeCurrentBuildDir$/xbe/xbe_file e:\$CMakeCurrentTargetName$ -f`
1. Set `Working directory` to `$ProjectFileDir$`

## Adding new tests

The `utils` directory has a script that may be used to generate a skeletal test suite.

### Documentation

Autogenerated documentation may be accessed
at [https://abaire.github.io/xemu-perf-tests](https://abaire.github.io/xemu-perf-tests/)

Some special Doxygen comments are used to describe test results on the website:

1. A detailed description attached to the `TestSuite` subclass (see `high_vertex_count_tests.h`)
2. Ideally a list of `@tc` custom commands in the documentation for the constructor method, explaining what each test is
   doing and/or is expected to display (see `high_vertex_count_tests.cpp`).

---

**NOTE:** For tests whose class name is not equal to the lower case version of the `suite_name` string passed to the
`TestSuite` constructor, a `kSuiteName` `private static constexpr const char *` should be created, containing the
`suite_name` value passed to the `TestSuite`. The documentation generation script will pick this up to allow downstream
scripts to discover the test metadata.

---

### Using nv2a log events from [xemu](https://xemu.app/)

1. Enable tracing of nv2a log events as normal (see xemu documentation) and exercise the event of interest within the
   game.
1. Duplicate an existing test as a skeleton.
1. Add the duplicated test to `CMakeLists.txt` and `main.cpp` (please preserve alphabetical ordering if possible).
1. Use [nv2a_to_pbkit](https://github.com/abaire/nv2a_to_pbkit) to get a rough set of pbkit invocations duplicating the
   behavior from the log. Take the interesting portions of the converted output and put them into the body of the test.
   You may wish to utilize some of the helper methods from `TestHost`   and similar classes rather than using the raw
   output to improve readability.

### Writing nv2a vertex shaders in assembly

See [the README in the nv2a_vsh_asm repository](https://github.com/abaire/nv2a_vsh_asm) for an overview.

`*.vsh` files are assembed via the `generate_nv2a_vshinc_files` function in CMakeLists.txt. Each vsh file produces a
corresponding `.vshinc` file that contains a C-style list of 32-bit integers containing the vertex shader operations.
This file is intended to be included from test source files to initialize a constant array which may then be used to
populate a `VertexShaderProgram` via `SetShader`.

For example:

```c++
// Note that the VertexShaderProgram does not copy this data, so it is important that it remain in scope throughout
// the use of the VertexShaderProgram object.
static const uint32_t kPassthroughVsh[] = {
#include "passthrough.vshinc"
};

// ...

  auto shader = std::make_shared<VertexShaderProgram>();
  shader->SetShader(kPassthroughVsh, sizeof(kPassthroughVsh));
  host_.SetVertexShaderProgram(shader);

```

Uniform values may then be set via the `VertexShaderProgram::SetUniform*` series of functions. By default, the 0th
uniform will be available in the shader as `c96`.

For example, a shader that takes a 4-element vertex might have the code:

```asm
#vertex vector 96
```

which would be populated via

```c++
  shader->shader->SetUniformF(0, -1.f, 1.5f, 0.f, 1.f);
```
