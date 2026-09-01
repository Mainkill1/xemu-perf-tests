# Run tests and retrieve results

This is the operator contract for the current XISO. Verify the release name,
source commit, SHA-256, and catalog size on the [landing page](../README.md)
before use. Do not substitute an older image with a similar filename.

The current full selection has 136 executable leaves and five structural
groups: 141 result records. The [catalog](generated/test-catalog.md) explains
every stable test ID. The [failure guide](generated/test-failure-guide.md) maps
a failed ID to the first emulator paths to inspect.

## Pick a workflow

| Need | Workflow |
| --- | --- |
| Repeatable xemu evidence bundle | Automated Windows runner |
| Quick visual/controller check | Manual xemu |
| Hardware observation/oracle candidate | Physical Xbox |
| Correctness comparison | Hash comparison |

Only one xemu process may run on a test host. Use release builds for timing.
Use diagnostic builds for assertions, symbols, validation, or counters; their
timings are not performance evidence.

## Automated xemu

The lab runner lives in `C:\xemu-lab\suite`; it is not part of this repository.
Check its `--help` because installed profiles follow the lab release.

Preflight:

1. Record xemu executable SHA-256 and embedded source version.
2. Verify XISO SHA-256 against the landing page or release manifest.
3. Close every other xemu process.
4. Fix renderer, scale, VSync, Xbox RAM, completion mode, and XISO.
5. Confirm the internal lab target is its dedicated disposable
   `C:\xemu-lab\suite\work\test.img`, never a game or user-provided HDD.
6. For A/B, calibrate work on baseline only; reuse that multiplier unchanged.

The current internal runner reformats that dedicated `work\test.img` before
every run. Guest `history` therefore does not persist between automated runs;
the extracted host run directory is the durable evidence. A public-safe runner
must instead create a new per-run disposable image at a new path and refuse any
pre-existing image. It must not accept, reuse, or format a user-provided HDD.

Run the complete current selection from Windows Command Prompt:

```bat
C:\xemu-lab\suite\python313\python.exe C:\xemu-lab\suite\run-suite.py ^
  --mode perf --full-suite ^
  --xemu C:\path\to\xemu.exe ^
  --guest-iso C:\path\to\xemu-perf-tests-eng467-time-spirit-2a65eba.iso ^
  --backend vulkan --scale 1 ^
  --completion-mode per_iteration --expected-record-count 141
```

For OpenGL, change only `--backend`. For another scale, change only `--scale`.
Add `--vulkan-validation` to a Vulkan correctness run; do not use that run for
timing.

An unmodified upstream xemu may lack the lab live-marker transport. For that
case only, add:

```text
--allow-missing-live-markers --host-telemetry off
```

This narrowly waives live-marker attribution. It cannot be combined with host
GDB samples. Record inventory, guest checks, functional hashes, and renderer
validation remain mandatory, so correctness is not relaxed. Timing from the
waived run is explicitly ineligible for a PR-grade performance claim.

Reduce an S3TC failure to its exact grouped route:

```bat
C:\xemu-lab\suite\python313\python.exe C:\xemu-lab\suite\run-suite.py ^
  --mode perf --test-id GameLoadComposite::10-S3tcSyncFactor ^
  --xemu C:\path\to\xemu.exe ^
  --guest-iso C:\path\to\xemu-perf-tests-eng467-time-spirit-2a65eba.iso ^
  --backend vulkan --scale 1 --completion-mode per_iteration ^
  --expected-record-count 13 --vulkan-validation
```

`--test-id` takes a legacy `Suite::Test` execution name. Stable IDs and legacy
mappings are in [`resources/catalog.json`](../resources/catalog.json). Prefer a
checked resolved plan when selecting independent composite children.

The runner preserves byte-exact `results.txt` and normally adds
`guest-config.json`, `normalized-results.json`, xemu/XISO identities, xemu log,
backend, scale, completion mode, host identity, and validation evidence. Treat
the run directory as one evidence unit. Never edit the guest result.

### Performance A/B

Correctness passes first. Both builds use the same XISO, config, renderer,
scale, completion mode, seed, and fixed work. Alternate process order, retain
raw samples, and compare distributions. Short runs establish execution or
direction only. Repeat tiny work inside the guest until samples last seconds.

Do not infer whole-emulator speed from one focused workload. Report stable ID,
path improved, fixed-work ratio, environment, and correctness status.

## Manual xemu

1. Start a release xemu build. Configure legally obtained MCPX, flash ROM,
   EEPROM, and HDD files.
2. Select the verified XISO as DVD and reset the guest.
3. Wait for the on-disc menu.
4. Allow three-second autorun, or press any controller input to cancel it.
5. Choose `Run Suite`, `Individual Tests`, or `Plans`.
6. Wait for final PASS/FAIL. A compatible soft failure pauses on light red for
   ten seconds; release A to advance early. It remains failed in the result.
7. Close xemu only after the result closes. Copy it from the test HDD without
   reformatting.

The XISO does not format the manual HDD. It creates and manages only its
configured output directory, `E:\xemu_perf_tests` by default. Existing current
results are archived there before a new manual run.

For unattended use, set `reboot_or_shutdown_delay` to `0` and enable shutdown.
For a person reading the display, use at least `30000` milliseconds. The
[sample config](../resources/sample-config.json) uses a 30-second hold.

The first existing configuration wins:

```text
E:\xemu_perf_tests\xemu_perf_tests_config.json
D:\xemu_perf_tests_config.json
```

E: therefore overrides the XISO config. Remove or replace stale E: config
before attributing an old selection to a new XISO.

## Physical Xbox

Boot the verified XISO through the owner's legal disc/dashboard workflow. The
primary output is functional evidence; host timing needs a separate contract.

Root entries are `Run Suite`, `Individual Tests`, `Results`, `System
Information`, `Plans`, `Settings`, `Time Spirit`, and `About/Controls`.
D-pad/left stick moves; A/Start selects; B/Back returns; Left/Right moves half a
page; X and Y perform the labeled suite/result actions; Black exits.

Hardware proof checklist:

1. Record release/catalog identity at boot.
2. Cancel autorun. Visit first, middle, and last pages of every suite.
3. Run one ordinary leaf, grouped route, plan, and full suite.
4. Confirm RUNNING progress changes during long stages.
5. Confirm PASS/FAIL, first failed stable ID, counts, and saved path.
6. Open `Results`; inspect current run, one record, and one graph.
7. Repeat the same plan. Hardware observations become oracle candidates only
   after independent matching runs with console/video provenance.

Host contracts and xemu screenshots are emulator evidence, not this hardware
gate.

## Result locations and safe copy

### Manual or physical Xbox

With a persistent HDD and the default `output_directory_path`, the guest writes:

```text
E:\xemu_perf_tests\results.txt
E:\xemu_perf_tests\resolved-plan-result.json
E:\xemu_perf_tests\history\results-YYYYMMDD-HHMMSS[-N].txt
```

The plan result exists only for resolved plans. Before a new run, current
`results.txt` moves into `history`. The guest never prunes history. If archival
fails, it refuses the new run instead of overwriting evidence.
`-N` is added only when multiple archives would otherwise have the same name.
Changing `output_directory_path` relocates current, plan, and history output
together; it does not relocate the read-only D: reference.

### Automated xemu

The same FATX paths exist only inside that run's disposable image. The current
lab runner extracts `results.txt` into the timestamped host run directory, then
reformats its dedicated image for the next run. Do not expect FATX `history` to
survive. Preserve and compare the host run directories.

Safe copy:

1. Wait for final screen; stop test activity.
2. Copy, do not move. Use the emulator HDD extractor or the console owner's
   dashboard/FTP transfer while idle.
3. Keep bytes unchanged. Do not open and save in an editor.
4. Compute copied-file SHA-256. Record XISO SHA-256, xemu build or Xbox
   provenance, backend, scale, video mode, and config beside it.
5. Parse the copy. Keep the E: original until hash and parsing succeed.

Bundled `D:\reference-results.txt` and
`D:\reference-results-provenance.txt` are read-only regression/performance
references for the Results UI. They are not retail-Xbox correctness goldens.

## Interpret results

| Field | Checks |
| --- | --- |
| `source_kat` | Generated input corpus |
| `work_checksum` | Operation order and amount |
| `result_checksum` | Semantic output |
| Named KAT | Critical pixel, tile, register, or state |
| `framebuffer_fnv1a64` | Guest framebuffer regression signature |
| Timing samples | Declared fixed-work scope cost |
| Group record | Child completion; never timing |

Statuses are separate:

- **Complete PASS:** expected records closed and required checks passed.
- **Soft failure:** guest continued; leaf and final run remain FAIL.
- **PARTIAL:** only closed records recovered; final totals unavailable. Useful
  for diagnosis, never correctness or performance qualification.
- **Crash/assert/device loss/hang:** incomplete emulator/infrastructure run.
- **Missing oracle:** execution may be valid; correctness is unverified.
- **Group failure:** inspect children; group has no independent timing.

A prior xemu hash detects change from that run. It does not prove Xbox pixels.
Never self-approve a new observed value. Hardware oracles require console
provenance, semantic contract and hash scope, repeated agreement, and review.

## Compare hashes

The comparator accepts run directories or `summary.json`, `results.json`, and
`normalized-results.json`:

```text
python utils/hash_compare.py BASELINE_RUN CANDIDATE_RUN [MORE_RUNS...] --json-out comparison.json
```

`1` means match, `0` mismatch, and `-` no baseline oracle. Exit 0 means all
candidates passed; 1 means mismatch/unverified; 2 means invalid input. Missing
records, extra records, zero eligible checks, and any mismatch fail closed.

## Failure handling

Preserve the first failure. A retry classifies repeatability; it does not erase
the original. Record first failed stable ID/alias, last RUNNING footer, XISO and
executable hashes, backend/scale/completion/config, host or console identity,
failure text, result SHA-256, and evidence directory. Use the
[failure guide](generated/test-failure-guide.md) for the first code path.

Before sharing evidence:

- confirm 141 records for an unfiltered current full suite;
- run `python3 utils/test_catalog.py --check` in source;
- preserve byte-exact guest result and comparison JSON;
- label evidence xemu-only or physical Xbox;
- state oracle provenance and compatibility allowances;
- never upload firmware, EEPROM, HDD images, commercial data, or guest RAM.

See [test-system.md](test-system.md) for architecture and
[adding-tests.md](adding-tests.md) before adding a workload.
