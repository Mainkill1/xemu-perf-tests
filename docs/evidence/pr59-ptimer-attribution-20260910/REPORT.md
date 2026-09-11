# PR59 PTIMER attribution: repeated snapshot results

> Follow-up: the [source and execution-order review](FOLLOWUP.md) confirms a five-for-five OpenGL second-position maximum pattern. Retained scheduler-trace attribution is underway; the original measurements below are preserved.

**Decision: HOLD / insufficient attribution.** The 20 predeclared measured captures completed. OpenGL's original large p99 observation did not repeat consistently: median paired improvement is **+0.177%**, with one of five pairs worse than 2%. Vulkan p99 remains concerning: median **−2.249%**, with three of five pairs worse than 2%. OpenGL maximum interval is also unfavorable in three pairs. These results do not establish a speedup or identify PTIMER as the cause.

The expanded production-translation-unit fixture passed **70/70 under Wine and 70/70 on native Windows**, exit 0. PR59's new commit adds tests only. No new timer policy, product optimization, merge, or baseline update was made. The original unfavorable observations remain preserved.

This is the bounded follow-up to [Mainkill1/xemu#40's handoff](https://github.com/Mainkill1/xemu/issues/40#issuecomment-5626660345), with code in [PR59](https://github.com/Mainkill1/xemu/pull/59) and evidence in [perf-tests PR27](https://github.com/Mainkill1/xemu-perf-tests/pull/27).

## Source and build identities

| Role | Exact source | Tree / executable |
| --- | --- | --- |
| Retained reference B | `c17591d59c270b352b72e648f5ed65e4b2a3e77e` | Tree `6824a5aa4d9ca288ac96092dc9244684e995b08d`; EXE SHA-256 `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Combined runtime candidate AM | `8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b` | Tree `20c4d0a4551a878485370329e9856766dca7c752`; EXE SHA-256 `6fb3dcdd998e67c18223fd4b6f0bfb74542bdc0b282d95776c5a27c8f8be7ab6` |
| Current PR59 head: additional tests only | `0043629b0bc13d2b34a1bf3c1008171ad8eecb8f` | Tree `c010d261e408219194f81dedcda30b85bcca9250`; unit EXE SHA-256 `d00c1c2d45eb0182b4098ba4138a23df38e90ef37085d4f071543b795e331238` |
| Original PR construction base | `bd1fecb93353272dda2a810991e28945de35b665` | Tree-identical to retained B |
| Fixed cycle baseline branch | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` | Retained baseline product executable above; no advance |
| Current main when this report was published | `e18ba8d6274cf227cc9e5ae1b5684f28ed911a99` | Not the original construction base; no advance during this investigation |

**Comparison scope:** AM vs the preserved baseline product tree and original construction parent. The effect of integrating this patch onto current `main` is **not measured**; it cannot inherit an incremental pass from these results. `0043629b` differs from `8da17c3e` only in `tests/unit/test-xbox-nv2a-ptimer.c` (+166 lines). The retained runtime binary was reused, not relabeled as a fresh full build of the test-only head.

Runtime builds use the historical Windows optimized/full-LTO/x86-64-v3 configuration, assertions, and matching DWARF. The unit rebuild used GCC 16.1.0 in toolchain image `ghcr.io/xemu-project/xemu-win64-toolchain-gcc@sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`, reusing the configured build/link dependencies read-only and rebuilding the fixture, PTIMER, and PRAMDAC translation units into separate scratch outputs. No baseline executable was rebuilt.

## Method and validity

The [plan](PLAN.md) was committed before measurement. Five paired observations per renderer, in alternating B/AM order, give 20 fresh-process 60-second captures. Four predeclared 10-second readiness pilots are retained and excluded from comparison. All 20 measured cells were admitted; **zero measured exclusions or retries**. The odd five-pair count leaves a 3:2 first-position imbalance within each renderer, reversed in the control renderer.

Host: Ryzen 9 6900HX, 16 logical processors, RTX 3070 Ti Laptop GPU, NVIDIA 581.95, Windows 10 22H2 build 19045.6466. Same immutable original v4 PGR2 snapshot, writable clone per run, keyboard reconnect then B-3, three-second warmup, no driving input, scale 1, CPU-reduction setting Off. Driver caches persisted normally; this is not a controlled cold-cache benchmark. Input/seed/config/script hashes are in [manifest.json](manifest.json).

The unchanged historical capture scripts used `CpuScheduler` tracing starting at steady state, PresentMon enabled, and Vulkan detail telemetry disabled. This is an instrumented diagnostic repeat. Occasional receipt queries and small file transfers occurred; heavy trace export and native unit execution were kept outside the timing campaign. It is not a claim of a perfectly idle host or production performance qualification.

Measured windows ran from 2026-09-11 00:07:37 to 00:45:46 UTC (September 10 PDT). All runs had zero focus-loss samples, ETW lost events/buffers, and not-responding samples. All 24 start images were inspected: expected stationary red-car race scene, 000 MPH, lap 1/3, position 6/6, no controller overlay. That establishes start readiness, **not equal completed work or an end-of-run gameplay oracle**.

Every cell preserved its seed hash and completed automatic capture/emulator/HDD-clone cleanup. Native unit execution followed the last capture and verified its own process exit. Original traces are closed and retained; no trace analyzer was left running.

## Timing results

**Improvement %:** positive is favorable; negative is unfavorable. `+bad` raw metrics use `100 × (B − AM) / B`; `+good` uses `100 × (AM / B − 1)`. Counts and present samples are context. Statistics below are medians/ranges of the **five paired improvements**, not ratios of medians, pooled percentiles, significance tests, or an automatic 2% acceptance rule.

| Renderer | Metric | Raw + | Median paired improvement | Paired improvement range | Pairs worse than 2% |
| --- | --- | --- | ---: | ---: | ---: |
| OPENGL | Logged flip cadence (Hz) | `+good` | -0.500% | -3.270% to +0.831% | 1/5 |
| OPENGL | Mean interval (ms) | `+bad` | -0.339% | -3.473% to +0.764% | 1/5 |
| OPENGL | p95 interval (ms) | `+bad` | -0.746% | -3.605% to +1.270% | 2/5 |
| OPENGL | p99 interval (ms) | `+bad` | +0.177% | -4.244% to +2.887% | 1/5 |
| OPENGL | Maximum interval (ms) | `+bad` | -4.201% | -31.110% to +15.446% | 3/5 |
| VULKAN | Logged flip cadence (Hz) | `+good` | -1.221% | -1.807% to +1.060% | 0/5 |
| VULKAN | Mean interval (ms) | `+bad` | -1.108% | -1.752% to +1.104% | 0/5 |
| VULKAN | p95 interval (ms) | `+bad` | -1.392% | -2.930% to +2.218% | 2/5 |
| VULKAN | p99 interval (ms) | `+bad` | -2.249% | -6.438% to +3.768% | 3/5 |
| VULKAN | Maximum interval (ms) | `+bad` | +8.694% | -21.745% to +15.249% | 1/5 |

Each pair's tail result is shown below so unfavorable runs cannot disappear into the median. Both p99 and maximum have raw direction `+bad`.

| Renderer / pair | Order | B p99 (ms) | AM p99 (ms) | p99 improvement | B max (ms) | AM max (ms) | Max improvement |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OPENGL / 1 | B → AM | 45.104 | 47.018 | -4.244% | 51.343 | 67.316 | -31.110% |
| OPENGL / 2 | AM → B | 46.953 | 46.945 | +0.017% | 62.604 | 52.934 | +15.446% |
| OPENGL / 3 | B → AM | 48.457 | 47.058 | +2.887% | 56.068 | 58.637 | -4.582% |
| OPENGL / 4 | AM → B | 47.845 | 47.397 | +0.936% | 60.941 | 55.518 | +8.899% |
| OPENGL / 5 | B → AM | 46.426 | 46.344 | +0.177% | 52.460 | 54.664 | -4.201% |
| VULKAN / 1 | AM → B | 46.967 | 46.459 | +1.082% | 72.256 | 65.974 | +8.694% |
| VULKAN / 2 | B → AM | 46.196 | 47.235 | -2.249% | 57.005 | 69.401 | -21.745% |
| VULKAN / 3 | AM → B | 45.199 | 48.109 | -6.438% | 69.931 | 70.871 | -1.344% |
| VULKAN / 4 | B → AM | 47.269 | 45.488 | +3.768% | 68.902 | 59.970 | +12.963% |
| VULKAN / 5 | AM → B | 44.793 | 47.361 | -5.733% | 72.313 | 61.286 | +15.249% |

The same broad slowdown is not consistent across renderer, pair, or metric. Vulkan's three adverse p99 pairs and OpenGL's maximum-interval tails remain reasons to hold acceptance. They do not justify restoring masked callbacks, changing IRQ publication, or changing the clock model without attribution. Scheduler variability, work equivalence, and timer-state interactions remain hypotheses.

### Raw measured runs

| Cell | Renderer | Build | Mean (ms) | p95 (ms) | p99 (ms) | Max (ms) | Logged cadence (Hz) | Interval count |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | OPENGL | B | 34.494 | 41.411 | 45.104 | 51.343 | 29.009 | 1740 |
| 2 | OPENGL | AM | 35.692 | 42.904 | 47.018 | 67.316 | 28.060 | 1681 |
| 3 | VULKAN | AM | 34.956 | 42.030 | 46.459 | 65.974 | 28.640 | 1716 |
| 4 | VULKAN | B | 34.943 | 42.081 | 46.967 | 72.256 | 28.627 | 1718 |
| 5 | VULKAN | B | 34.557 | 41.512 | 46.196 | 57.005 | 28.934 | 1737 |
| 6 | VULKAN | AM | 35.163 | 42.363 | 47.235 | 69.401 | 28.411 | 1706 |
| 7 | OPENGL | AM | 35.210 | 42.705 | 46.945 | 52.934 | 28.427 | 1704 |
| 8 | OPENGL | B | 35.481 | 42.726 | 46.953 | 62.604 | 28.193 | 1694 |
| 9 | OPENGL | B | 35.254 | 42.595 | 48.457 | 56.068 | 28.357 | 1703 |
| 10 | OPENGL | AM | 35.659 | 43.460 | 47.058 | 58.637 | 28.068 | 1682 |
| 11 | VULKAN | AM | 35.286 | 42.106 | 48.109 | 70.871 | 28.356 | 1701 |
| 12 | VULKAN | B | 34.711 | 41.528 | 45.199 | 69.931 | 28.784 | 1729 |
| 13 | VULKAN | B | 34.812 | 41.709 | 47.269 | 68.902 | 28.741 | 1724 |
| 14 | VULKAN | AM | 34.428 | 40.784 | 45.488 | 59.970 | 29.046 | 1743 |
| 15 | OPENGL | AM | 35.622 | 43.053 | 47.397 | 55.518 | 28.058 | 1683 |
| 16 | OPENGL | B | 35.502 | 42.734 | 47.845 | 60.941 | 28.199 | 1690 |
| 17 | OPENGL | B | 34.885 | 42.204 | 46.426 | 52.460 | 28.694 | 1720 |
| 18 | OPENGL | AM | 34.660 | 41.668 | 46.344 | 54.664 | 28.862 | 1731 |
| 19 | VULKAN | AM | 34.849 | 41.979 | 47.361 | 61.286 | 28.668 | 1722 |
| 20 | VULKAN | B | 34.467 | 40.784 | 44.793 | 72.313 | 29.022 | 1740 |

Full precision, order, source identity, UTC windows, cleanup, and counters are in [runs.json](runs.json) and [per-run.csv](per-run.csv); [paired-results.json](paired-results.json) contains every comparison. The 34,264 measured frame intervals plus 1,151 excluded-pilot intervals are published in [frame-intervals.csv.gz](frame-intervals.csv.gz).

Mean and nearest-rank p95/p99 were independently recomputed from all complete intervals whose beginning and end fall inside the monotonic measurement window. Measured frame windows cover 60.013–60.116 seconds. Logged flip-cadence coverage is separately 55.144–55.274 seconds because that existing log uses a different window. Its count/elapsed denominator is published separately. Do not divide the interval count by the cadence duration or label the cadence displayed FPS, guest virtual time, or fixed CPU/GPU work.

### Historical observations retained

The [original full-precision comparison](https://github.com/Mainkill1/xemu-perf-tests/blob/b180091ccfc14d198426a0802b4cb5c9ad7153cc/docs/evidence/ptimer-main-20260909/pgr2/comparison.json) was one non-interleaved observation per condition. It remains part of the evidence:

| Original snapshot metric | B | AM | Raw + | Improvement |
| --- | ---: | ---: | --- | ---: |
| OpenGL mean (ms) | 35.122224 | 37.694658 | `+bad` | −7.324233% |
| OpenGL p95 (ms) | 42.308 | 45.400 | `+bad` | −7.308310% |
| OpenGL p99 (ms) | 46.086 | 52.745 | `+bad` | −14.449073% |
| Vulkan p99 (ms) | 45.186 | 46.296 | `+bad` | −2.456513% |

Earlier approximately neutral/favorable PGR2 fresh-start observations and contextual Morrowind measurements are preserved in the [archived PR description](historical-pr59-description-8da17c3e.md). They use different routes/times and do not cancel adverse snapshot tails. Old text is historical, including its obsolete missing-image and source-identity statements; this report controls the current disposition.

## Production-path characterization

| Test group | Cases | Wine | Native Windows | What it establishes |
| --- | ---: | --- | --- | --- |
| Existing PTIMER controls | 24 | PASS | PASS | Existing arithmetic, masks, acknowledgment, clocks, wrap, restore controls still pass |
| Timebase changes × observation modes | 45 | PASS | PASS | Nine change types × poll, callback-first, masked poll, already-pending, masked acknowledgment |
| TIME write backward | 1 | PASS | PASS | Rebuilds a future deadline without spuriously latching pending |
| Total | 70 | Exit 0 | Exit 0; cleanup complete | Production PTIMER/PRAMDAC translation units under the established fixture |

The nine change types cover core frequency, numerator, denominator, TIME low/high, core stop/restart, actual NVPLL register write, and numerator/denominator stop/restart. See the [test-only commit](https://github.com/Mainkill1/xemu/commit/0043629b0bc13d2b34a1bf3c1008171ad8eecb8f), [per-case results](timebase-unit-results.json), and [native receipt](native-receipt.json).

The handoff example is confirmed on this implementation: at 100 ns, increasing the frequency across an armed target queues a deadline at 100 ns without latching inside the setter; the next status read or callback reconciles the overdue alarm and advances its epoch. Masked observation retains guest pending state without a queued callback, and acknowledgment does not resurrect the elapsed alarm. **An already-overdue due-now callback is not the future-distance zero-delay defect.** These new cases characterize observation order; they do not establish Xbox hardware's immediate IRQ policy.

The fixture has controlled clock/timer/IRQ stubs. It is not the full NV2A IRQ aggregator, Windows scheduler, or a guest gameplay benchmark. Historical 576/576 generic timer controls and five expected-old-code failures remain credited in the [earlier native report](https://github.com/Mainkill1/xemu-perf-tests/blob/e49d8ef33d3aa6efa9722502ef5a6254a824b986/docs/evidence/ptimer-main-20260909/REPORT.md); neither was rerun in this bounded pass.

## Fixed-work and full-suite admission

The installed output-only runner still rejects a valid metadata-absent PGRAPH record. The pair controller still lacks output-only forwarding. We executed the actual extracted validator functions against synthetic records: installed code rejects absent metadata; the reviewed [perf-tests PR14](https://github.com/Mainkill1/xemu-perf-tests/pull/14) child accepts it and rejects wrong framebuffer hashes and unexpected metadata. The installed unexpected-metadata control raises an AttributeError; that is a non-graceful rejection, not a successful contract. [Results and source hashes](fixed-work-admission.json), [reproduction](check-admission.py).

This is a source/function admission test, not native fixed-work execution. PR14 already owns the correction and was updated with the finding. Its complete parent/child transport, artifact/catalog binding, and native baseline calibration still require qualification; no wholesale runner replacement or gate waiver was made here. Per-thread CPU is also not established by its retained whole-process CPU measurement.

The newer **157-case XISO image exists** (suite source `61012b4e702fbb46a02d813e71f2159a109a1c29`). A historically missing 154-case image is not the current blocker. Results on other PR heads do not qualify PR59. No new full-XISO, PGR2 fresh-start, or Morrowind snapshot campaign ran in this bounded attribution pass; those remain final acceptance gates. The previous Morrowind initial/v5 checks stay credited, while the original-v4 reload/controller overlay on both builds remains [xemu#61](https://github.com/Mainkill1/xemu/issues/61). Morrowind qualification uses snapshots, not a full-start route.

## Resource and attribution limits

| Measurement | This campaign | Remaining requirement |
| --- | --- | --- |
| Host elapsed, guest interval/flip records | Published per run | Do not equate cadence to fixed guest work |
| Scheduler ETL | Captured, closed, hashes retained | Symbolized per-thread CPU/wait attribution |
| PTIMER callback / reconcile / timer-list counts | Not collected | Matched host-only diagnostic counters |
| IRQ recomputations / effective transitions | Not collected | Full NV2A-path measurement, not only fixture IRQ stub |
| Main-loop wait returns / scheduler wake causes | Not attributed | Correlate ready/notify/return/dispatch timing |
| GPU / power / VRAM sensors | Partial tail only | [perf-tests#24](https://github.com/Mainkill1/xemu-perf-tests/issues/24); no full resource pass |
| Known guest operation count / terminal oracle | Not admitted | Strict fixed-work calibration on B and AM |

Missing measurements are explicit `null` in each run. No zero callback/cost claim is inferred from them. Four-factor B/A/M/AM builds and the controlled wait interaction were not run. The repeat is enough to reject a simple claim that the earlier large OpenGL p99 change is consistent; it is insufficient to accept PR59 or localize the remaining adverse tails.

## Decision and remaining gates

**Retain PR59 as a draft. This pass ends with insufficient attribution, not a speculative production fix.** The existing arithmetic/state repairs and characterization evidence remain useful.

1. Qualify the already-reviewed fixed-work transport/metadata correction and native baseline/output oracle. Keep both baseline and candidate tied to the same workload/tool revision.
2. Attribute remaining tails with matched timer/IRQ/wait counters and symbolized per-thread CPU. If adverse behavior persists with comparable completed work, use the explicitly defined B/A/M/AM factor split; do not relabel a mixed change arithmetic-only.
3. Check the wait interaction using a controlled current-cycle extraction if notification/wait evidence warrants it. Fewer callbacks do not alone prove fewer wakeups.
4. Resolve the original-v4 readiness gate separately and complete both-renderer full XISO, Morrowind snapshot, PGR2 fresh-start, and resource qualification on the actual intended integration head. Record both candidate-vs-previous-main and candidate-vs-fixed-baseline results.

## Reproduction and evidence retention

From the evidence repository root, recompute the published frame/paired results without launching xemu:

```sh
python3 docs/evidence/pr59-ptimer-attribution-20260910/check-results.py
python3 -m unittest discover -s utils -p test_summarize_snapshot_pairs.py -v
python3 utils/summarize_snapshot_pairs.py docs/evidence/pr59-ptimer-attribution-20260910/runs.json --expected-pairs 5 --renderer OPENGL --renderer VULKAN --output pr59-paired-results.recomputed.json
```

The capture controller is [run_snapshot_campaign.ps1](../../../utils/run_snapshot_campaign.ps1), byte-identical to the executed controller and pinned in the manifest. In the supported interactive PowerShell 7 session it was invoked twice, first `-ManifestPath <site-local-manifest> -Phase pilot`, then `-ManifestPath <site-local-manifest> -Phase measured`, with visual admission between them. The private manifest supplies local executable/input/output paths for the public identities. The pinned historical runner and its dependencies are prerequisites; this wrapper is not a self-contained distribution of those tools or the game/snapshot assets.

The exact isolated unit-build script is [rebuild-unit.py](rebuild-unit.py). Within the pinned toolchain, `/src` was the read-only configured `8da17c3e` source/build, and `/scratch` contained the `0043629b` fixture and writable output/cache. It replays the matching entries from `compile_commands.json` and the `ninja -t commands tests/unit/test-xbox-nv2a-ptimer.exe` link command. The output unit executable was invoked under Wine on the build host, then directly on native Windows after capture shutdown. Both returned 0; the 70 expected test names were checked. Runtime source/fixture/unit hashes are in [timebase-unit-results.json](timebase-unit-results.json).

The complete original ETLs, capture metadata, start screenshots, raw frame/flip logs, and partial sensors remain on the authorized test host under each immutable `run_id`. [retained-artifacts.json](retained-artifacts.json) publishes names, sizes and SHA-256 values for ETLs, images, measured frame logs, frame summaries and sensor files. About 41.3 GB is identified there. Raw host traces and copyrighted screenshots are not public attachments. Public frame intervals and per-run records allow timing arithmetic to be independently reproduced; they do not expose the private traces' causal detail. [attempts.json](attempts.json) preserves dispatcher and unit-build setup failures; no measured slow run was excluded. [SHA256SUMS](SHA256SUMS) covers the published bundle.
