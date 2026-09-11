> Archived PR59 description retrieved before the test-only `0043629b` update on September 10, 2026. Private host addresses are redacted and formatting whitespace is normalized; other historical text is retained. This is historical evidence, not the current qualification decision. See REPORT.md in this folder for the completed attribution repeat.

# fix/ptimer-main-qualification

**Status:** Testing / HOLD — targeted timer controls pass, but performance acceptance remains held
**PR:** [#59](https://github.com/Mainkill1/xemu/pull/59)
**Issue:** [#40](https://github.com/Mainkill1/xemu/issues/40), [#39](https://github.com/Mainkill1/xemu/issues/39), and compatibility follow-up [#61](https://github.com/Mainkill1/xemu/issues/61)

**Stable baseline:** `baseline` at `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; accepted product tree `6824a5aa4d9ca288ac96092dc9244684e995b08d`; executable SHA-256 `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b`
**Prior candidate:** [PR #48](https://github.com/Mainkill1/xemu/pull/48), a different S-based source whose results do not qualify this extraction
**Current candidate:** `8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b`, tree `20c4d0a4551a878485370329e9856766dca7c752`; executable SHA-256 `6fb3dcdd998e67c18223fd4b6f0bfb74542bdc0b282d95776c5a27c8f8be7ab6`

**Build:** Windows optimized build, full LTO, x86-64-v3, debug assertions
**Test:** Native PTIMER 24/24 and generic timer 576/576 pass; five exact-baseline negative controls fail as intended and repaired counterparts pass
**Profile:** One non-interleaved 60-second PGR2 capture per renderer/launch mode versus retained matching baseline, scale 1 and identical seed/configuration

---

## Summary

**Current result:**
Targeted timer correctness controls pass. Snapshot OpenGL mean/p95/p99 are -7.32%/-7.31%/-14.45% and Snapshot Vulkan p99 is -2.46%, exceeding the 2% rejection gate in one pair.

**Headline:**
The candidate repairs the addressed timer failures but remains unmerged until fixed-work performance, callback/wakeup resources, compatibility, and full-suite gates complete.

**Next:**
Complete strict output-only contracts, baseline calibration, seeded GL/Vulkan fixed-work comparison, callback/resource attribution, old-v4 readiness, and valid full-XISO qualification.

---

# Investigation

## Why This Patch Exists

**Observed problem:**
Masked PTIMER alarms retain host callbacks even when they cannot assert an interrupt. Separate truncating guest-clock conversions can schedule a positive future alarm early or at the current host time.

**Profiling evidence:**
Five exact-baseline negative controls reproduce arithmetic/state failures. Host callback/wakeup cost is not yet measured. Initial PGR2 Snapshot results contain unfavorable observations above 2%.

**Suspected cause:**
Guest alarm state is coupled to host timer-object lifetime, and inverse deadline calculation truncates both forward clock quantization stages without preserving phase.

**Why this is worth investigating:**
Correct timer deadlines and masked-alarm state are baseline correctness requirements. Retiring unnecessary callbacks may also reduce host wakeups, but that benefit must be measured separately.

## Patch Hypothesis

**What we plan to change:**
Keep `alarm_armed` independent of the host callback, reconcile elapsed state at acknowledgement/clock/state transitions, and invert both forward-clock quantizations with phase-aware ceilings.

**Why it should be faster:**
Masked alarms no longer require callbacks solely to preserve guest state, potentially reducing timer modifications and host wakeups.

**Expected result:**
Positive future distance never produces a same-time deadline; masked alarms retain polled/reenabled state without a queued callback; fixed guest work remains correct.

**Possible risks:**
Interrupt timing, acknowledgment, clock stop/restart, PLL changes, VMState version compatibility, callback churn, or workload timing regressions.

---

# Processing Flow

## Current

### Current behavior

1. Guest arms a PTIMER alarm.
2. Host callback remains queued even when its interrupt is masked.
3. Guest distance is converted through two truncating divisions.
4. Positive distance may become an early or zero-delay host deadline.
5. Timer-object state is used to infer guest alarm state.

## Candidate

### Candidate behavior

1. Guest `alarm_armed` state is explicit.
2. Masked or stopped host callbacks can be canceled.
3. Deadline inversion uses phase-aware two-stage ceilings.
4. Acknowledgment, clock/PLL changes, and VMState restore reconcile state.
5. Reenable schedules the next valid future callback while preserving pending behavior.

### Processing Difference

| Area | Current | Candidate | Expected Effect |
| --- | --- | --- | --- |
| CPU work | Masked callback can still execute | Masked callback retired | Potentially fewer wakeups |
| Deadline math | Two truncating inversions | Phase-aware two-stage ceilings | Future alarm stays future |
| Guest state | Coupled to host timer | Explicit `alarm_armed` | Preserve polling/reenable |
| Clock changes | Partial rescheduling contract | Central reconciliation | Consistent deadlines |
| VMState | No explicit armed field | v5 field; v4 reconstruction | Defined migration behavior |

---

# Code Changes

- Add explicit PTIMER `alarm_armed` state and VMState v5 handling.
- Correct future-deadline arithmetic with phase-aware two-stage ceilings and wide intermediates.
- Reconcile masked, acknowledged, stopped, restarted, overdue, and PLL-rate transitions.
- Extend the production translation-unit unit target with fractional, phase, range, wrap, mask, acknowledgment, rate-change, and restore controls.
- Preserve shared generic timer behavior and exact-baseline negative controls.

**Main code path:** `hw/xbox/nv2a/ptimer.c`, PRAMDAC clock updates, NV2A VMState, and PTIMER production-unit tests
**Commits:** [PR commit list](https://github.com/Mainkill1/xemu/pull/59/commits)

---

# Profiling

## Baseline Bottleneck

| Measurement | Stable Baseline | Prior Candidate | Current Candidate |
| --- | ---: | ---: | ---: |
| Exact negative controls | 5/5 fail as intended | Different source | 5/5 repaired counterparts pass |
| Native PTIMER controls | Baseline control build | Different source | 24/24 pass |
| Generic timer target | 576/576 | Different source | 576/576 |
| PTIMER callback/wakeup cost | Not measured | Not comparable | Not measured |

**Profile evidence:** [Native timer and Morrowind evidence](https://github.com/Mainkill1/xemu-perf-tests/blob/e49d8ef33d3aa6efa9722502ef5a6254a824b986/docs/evidence/ptimer-main-20260909/REPORT.md)

## After Patch

**Bottleneck status:** Worse in initial PGR2 Snapshot observations; cause still testing.

**What changed in the profile:**
Snapshot has adverse tails above the 2% gate. FreshBoot is approximately neutral/favorable in one pair. The data is insufficient for acceptance and does not identify cause.

**New limiting path:**
Strict fixed-work timing, callback/wakeup attribution, old-v4 readiness, and valid full-suite evidence.

---

# Performance Results

## Improvement Convention

Every percentage comparison in this report is **Improvement %**: positive is good and negative is bad. The `Raw +` cell declares how a larger raw value is treated.

| Raw + | Raw metric direction | Improvement % |
| --- | --- | --- |
| `+good` | Higher is better, such as FPS or completed work | `100 × (candidate / reference - 1)` |
| `+bad` | Lower is better, such as interval or CPU time | `100 × (reference - candidate) / reference` |
| `N/A` | Context only or no desired direction | `N/A` with the limitation explained |

Guest display-write intervals are not rendered FPS. Historical raw Delta fields below retain their original direction and are not normalized results.

## Headline Results

| Workload | Renderer | Metric | Raw + | Stable | Prior | Candidate | Improvement vs Stable (+ good / - bad) | Improvement vs Prior (+ good / - bad) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| PGR2 Snapshot | Vulkan | p99 interval | `+bad` | 45.186 ms | N/A | 46.296 ms | **-2.46%** | N/A |
| PGR2 Snapshot | OpenGL | mean interval | `+bad` | 35.122 ms | N/A | 37.695 ms | **-7.32%** | N/A |
| PGR2 Snapshot | OpenGL | p95 interval | `+bad` | 42.308 ms | N/A | 45.400 ms | **-7.31%** | N/A |
| PGR2 Snapshot | OpenGL | p99 interval | `+bad` | 46.086 ms | N/A | 52.745 ms | **-14.45%** | N/A |

**Overall:**
Snapshot results cross the 2% rejection gate in one non-interleaved pair. FreshBoot observations do not offset that result or prove causation.

---

## Frame Performance

| Workload | Renderer | Metric | Raw + | Stable | Prior | Candidate | Improvement vs Stable (+ good / - bad) | Improvement vs Prior (+ good / - bad) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| PGR2 Snapshot | Vulkan | mean interval | `+bad` | 34.484 ms | N/A | 34.627 ms | -0.42% | N/A |
| PGR2 Snapshot | Vulkan | p95 interval | `+bad` | 40.910 ms | N/A | 41.338 ms | -1.05% | N/A |
| PGR2 Snapshot | Vulkan | p99 interval | `+bad` | 45.186 ms | N/A | 46.296 ms | -2.46% | N/A |
| PGR2 Snapshot | OpenGL | mean interval | `+bad` | 35.122 ms | N/A | 37.695 ms | -7.32% | N/A |
| PGR2 Snapshot | OpenGL | p95 interval | `+bad` | 42.308 ms | N/A | 45.400 ms | -7.31% | N/A |
| PGR2 Snapshot | OpenGL | p99 interval | `+bad` | 46.086 ms | N/A | 52.745 ms | -14.45% | N/A |
| PGR2 FreshBoot | Vulkan | mean / p95 / p99 interval | `+bad` | 33.333 / 33.412 / 34.497 ms | N/A | 33.343 / 33.554 / 34.341 ms | -0.03% / -0.42% / +0.45% | N/A |
| PGR2 FreshBoot | OpenGL | mean / p95 / p99 interval | `+bad` | 33.343 / 33.822 / 36.059 ms | N/A | 33.333 / 33.740 / 34.440 ms | +0.03% / +0.24% / +4.49% | N/A |
| Morrowind context | Vulkan | cadence / p95 / p99 | Mixed | 23.723/s / 47.990 / 57.134 ms | N/A | 24.632/s / 47.619 / 55.640 ms | Context only | N/A |
| Morrowind context | OpenGL | cadence / p95 / p99 | Mixed | 32.798/s / 38.098 / 42.848 ms | N/A | 34.254/s / 37.712 / 41.896 ms | Context only | N/A |

Morrowind ran at a different time and is contextual only. It cannot offset PGR2 Snapshot or establish patch causality.

---

# xiso Results

**Scope:** Invalid baseline attempts only; no valid performance suite
**Repeats:** 2 OpenGL setup/transport attempts
**Cases:** 149 PASS / 1 FAIL of 150 emitted in each attempt; four required xemu-only records omitted

| Group / Family | Renderer | Metric | Raw + | Stable | Prior | Candidate | Improvement vs Stable (+ good / - bad) | Improvement vs Prior (+ good / - bad) |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| Full XISO attempt | OpenGL | Correctness records | `N/A` | 149 PASS / 1 FAIL / 4 omitted | N/A | Not run validly | N/A | N/A |
| Full XISO | Vulkan | Duration | `+bad` | Not run validly | N/A | Not run validly | N/A | N/A |

**Full per-test results:** [Preserved baseline campaign](https://github.com/Mainkill1/xemu-perf-tests/blob/b180091ccfc14d198426a0802b4cb5c9ad7153cc/docs/evidence/baseline-campaign-20260909/REPORT.md)

### Largest Improvements

| Test | Renderer | Metric | Raw + | Stable | Candidate | Improvement % (+ good / - bad) |
| --- | --- | --- | --- | ---: | ---: | ---: |
| N/A | Both | Duration | `+bad` | Invalid attempt | Not run | N/A |

### Largest Regressions

| Test | Renderer | Metric | Raw + | Stable | Candidate | Improvement % (+ good / - bad) |
| --- | --- | --- | --- | ---: | ---: | ---: |
| N/A | Both | Duration | `+bad` | Invalid attempt | Not run | N/A |

**Unstable / excluded:**
Both OpenGL attempts failed strict admission and are not timing results or golden oracles.

---

# Resource Results

| Metric | Renderer | Raw + | Stable | Prior | Candidate | Improvement vs Stable (+ good / - bad) | Improvement vs Prior (+ good / - bad) |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| PTIMER callbacks per fixed work | Both | `+bad` | Not measured | N/A | Not measured | N/A | N/A |
| Host wakeups per fixed work | Both | `+bad` | Not measured | N/A | Not measured | N/A | N/A |
| Host CPU/GPU time per fixed work | OpenGL | `+bad` | Not measured | N/A | Not measured | N/A | N/A |
| Host CPU/GPU time per fixed work | Vulkan | `+bad` | Not measured | N/A | Not measured | N/A | N/A |
| RAM / VRAM | Both | `+bad` | Not measured | N/A | Not measured | N/A | N/A |

**Resource result:**
Reduced callback scheduling does not establish a host-efficiency, power, or resource-saving claim until callback/wakeup and fixed-window resources are measured.

---

# Correctness

| Check | OpenGL | Vulkan |
| --- | --- | --- |
| Functional | PTIMER 24/24; generic timer 576/576 shared results | PTIMER 24/24; generic timer 576/576 shared results |
| Hash / oracle | Five exact-baseline negative controls fail as intended; repaired controls pass | Same shared controls |
| Validation errors | No blocking error in focused controls | No blocking error in focused controls |
| Visual output | Initial Morrowind/PGR2 static scene gates pass | Initial Morrowind/PGR2 static scene gates pass |
| Guest progression | PGR2 2/2 mode captures complete; sustained readiness unfinished | PGR2 2/2 mode captures complete; sustained readiness unfinished |
| Other | Candidate v5 roundtrip passes; old-v4 reaches controller overlay on both builds | Same shared compatibility limit |

**Correctness result:**
The addressed timer controls pass. Old-v4 readiness remains unresolved on baseline and candidate, and full snapshot compatibility is not accepted.

---

# Validation Status

| Test | OpenGL | Vulkan |
| --- | --- | --- |
| Targeted patch test | Pass — PTIMER 24/24 and generic 576/576 shared | Pass — same shared controls |
| Representative/partial xiso | Regression — invalid attempt has 1 failure and 4 omissions | Not run — transport/selection gates |
| Profiling comparison | Regression signal — Snapshot exceeds 2% | Regression signal — Snapshot p99 exceeds 2% |
| Resource comparison, if relevant | Not run — callbacks/wakeups/resources pending | Not run — callbacks/wakeups/resources pending |
| Morrowind snapshot | Pass, limited — initial smoke/images | Pass, limited — initial smoke/images |
| PGR2 fresh-start | Testing — one approximately neutral/favorable pair | Testing — one approximately neutral/favorable pair |
| Full xiso | Not run — strict transport, selection, and DMA-report gates remain open | Not run — strict transport, selection, and DMA-report gates remain open |
| Final visual validation | Not run — static scene/UI only | Not run — static scene/UI only |
| VMState old-v4 readiness | Not run to acceptance — #61 | Not run to acceptance — #61 |

---

# Tradeoffs / Regressions

**Performance regressions:**
Snapshot OpenGL mean/p95/p99 and Vulkan p99 exceed the 2% unfavorable gate in one non-interleaved pair.

**Correctness regressions:**
The timer controls pass, but old-v4 readiness remains unresolved on both baseline and candidate.

**Resource tradeoffs:**
Callback/wakeup, CPU/GPU, RAM, VRAM, and power effects are unmeasured.

**Other concerns:**
Static captures do not prove sustained progression or causation. Strict XISO selection, output transport, and DMA-report gates remain open.

---

# Decision

**Result:** Hold

**Why:**
Unfavorable Snapshot observations, missing fixed-work/resource evidence, unresolved compatibility, and invalid full-suite attempts prevent acceptance.

**Integration path:**
Keep draft. Do not merge or advance baseline until all listed gates pass on the exact head.

**Follow-up:**

- Approve and deploy strict output-only runner contracts.
- Run baseline-only calibration and seeded fixed-work GL/Vulkan comparison.
- Measure PTIMER callbacks, host wakeups, and comparable host resources.
- Resolve old-v4 readiness in #61.
- Complete valid full-XISO OpenGL/Vulkan qualification.

---

# Evidence

- **Stable results:** [Retained baseline and PGR2 comparison](https://github.com/Mainkill1/xemu-perf-tests/blob/b180091ccfc14d198426a0802b4cb5c9ad7153cc/docs/evidence/ptimer-main-20260909/pgr2/README.md)
- **Prior candidate results:** [PR #48](https://github.com/Mainkill1/xemu/pull/48) — different source, contextual only
- **Candidate results:** [Native timer/Morrowind report](https://github.com/Mainkill1/xemu-perf-tests/blob/e49d8ef33d3aa6efa9722502ef5a6254a824b986/docs/evidence/ptimer-main-20260909/REPORT.md)
- **Raw/per-test data:** [Full-precision PGR2 comparison](https://github.com/Mainkill1/xemu-perf-tests/blob/b180091ccfc14d198426a0802b4cb5c9ad7153cc/docs/evidence/ptimer-main-20260909/pgr2/comparison.json)
- **Profiling:** Callback/wakeup profile not yet collected
- **Resource capture:** N/A — fixed-window comparison pending
- **Visual evidence:** Linked from PGR2 and native reports
- **PR:** [#59](https://github.com/Mainkill1/xemu/pull/59)
- **Issue:** [#40](https://github.com/Mainkill1/xemu/issues/40), [#39](https://github.com/Mainkill1/xemu/issues/39), [#61](https://github.com/Mainkill1/xemu/issues/61)
- **Related Wiki:** [Performance PR template](https://github.com/Mainkill1/xemu/blob/main/evidence/wiki-xiso-per-test/PERFORMANCE_PR_TEMPLATE.md)

---

# Final Summary

**Status:** Testing / HOLD

The candidate repairs the targeted PTIMER arithmetic and masked-alarm failures, and focused timer controls pass. One PGR2 Snapshot comparison exceeds the 2% unfavorable gate on OpenGL and Vulkan p99, while fixed-work resources, old-v4 readiness, and full-XISO qualification remain incomplete. Keep the draft unmerged and leave baseline unchanged.

# Preserved Historical Report

> **Historical raw-delta warning:** The following original PR body is retained verbatim. Any raw `Delta`, `Average delta`, `vs Stable`, or similarly named field uses its original formula and direction; do not treat it as a normalized `Improvement %` result. Missing values are not zero.

# fix/ptimer-main-qualification

**Status:** Testing — correctness controls pass; performance acceptance remains held
**PR:** [#59](https://github.com/Mainkill1/xemu/pull/59)
**Issues:** [#40](https://github.com/Mainkill1/xemu/issues/40), [#39](https://github.com/Mainkill1/xemu/issues/39)

**Stable baseline:** `9f618d6d8c4c446ef023955f3d4de22f661f61a4` / `3489fdcc…fb16b`
**Prior candidate:** [PR #48](https://github.com/Mainkill1/xemu/pull/48), different S-based source
**Current candidate:** `8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b` / `6fb3dcdd…e7ab6`

**Build:** `build host`
**Test:** `Windows test host`, Session 1 GUI dispatcher
**Profile:** Official Windows optimized build, full LTO, x86-64-v3, debug assertions

## Summary

**Current result:** Testing. Native timer controls pass, but initial PGR2 Snapshot comparisons have unfavorable intervals above the 2% gate.
**Headline:** Snapshot OpenGL mean/p95/p99 guest intervals increased 7.32%/7.31%/14.45%; Snapshot Vulkan p99 increased 2.46%. These single retained-baseline comparisons are observations, not causal estimates.
**Next:** Complete strict fixed-work GL/Vulkan comparison and callback/wakeup attribution. Keep the candidate unmerged.

# Investigation

## Why This Patch Exists

**Observed problem:** Masked PTIMER alarms retain host callbacks, while deadline conversion can schedule a future guest alarm early or at the current host time.
**Profiling evidence:** Source inspection and exact baseline negative controls reproduce all five arithmetic/state failures. Callback/wakeup cost is not yet measured.
**Suspected cause:** Host callback lifetime doubles as guest alarm state, and two truncating clock conversions discard positive fractional distance.
**Why this is worth investigating:** The defects affect timer correctness and may cause avoidable host wakeups in PGR2 and other timer-heavy workloads.

## Patch Hypothesis

**What changes:** Preserve guest alarm state independently, retire masked callbacks, and invert both guest-clock quantizations with phase-aware ceilings.
**Why it may help:** Masked alarms stop waking the host when they cannot assert an interrupt, while future deadlines remain future deadlines.
**Expected result:** Baseline failure controls pass on the candidate; callback/wakeup counts fall in masked fixed work without a greater-than-2% renderer regression.
**Possible risks:** Timer phase, interrupt acknowledgment, PLL transitions, migration compatibility, and renderer workload cadence.

## Goal

A masked PTIMER alarm currently leaves a host callback queued. Canceling it without preserving the guest alarm would lose pending state needed by polling, acknowledgment, interrupt reenable and snapshots. Separately, two truncating conversions can produce an early or zero host deadline for a future guest alarm.

Avoid unnecessary masked callbacks while preserving those behaviors, and schedule future alarms correctly. The two defects have separate negative controls; performance measurements qualify the combined patch and do not attribute every change to masking alone.

## Changes

Keep explicit `alarm_armed` state when masked or stopped host callbacks are canceled. Reconcile elapsed state before acknowledgment and enable/rate/time changes. Route NVPLL writes through clock-change handling. Preserve pending interrupts, serialize armed state in NV2A version 5, recover it from version 4 timer state, and clear fields absent from older streams.

Invert both forward-clock quantizations with phase-aware ceilings, handle source wrap, and bound signed deadlines. Changes are confined to PTIMER/PRAMDAC, associated NV2A state/VMState fields, and the existing unit-test target. This is the focused current-main extraction of [PR #48](https://github.com/Mainkill1/xemu/pull/48).

## Source and baseline

| Role | Exact identity |
| --- | --- |
| Fixed cycle baseline and previous accepted main | `9f618d6d8c4c446ef023955f3d4de22f661f61a4`, tag `baseline/cycle-01-start` |
| Current `main` at this report | `137a0b9c22df6906c351c06cf5797d9104546598`; only the maintained PR template was added after the cycle start |
| Equivalent baseline product source / compiled source | `bd1fecb93353272dda2a810991e28945de35b665` / `c17591d59c270b352b72e648f5ed65e4b2a3e77e` |
| Reused baseline executable SHA-256 | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Candidate source | `8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b` |
| Candidate tree | `20c4d0a4551a878485370329e9856766dca7c752` |
| Candidate executable SHA-256 | `6fb3dcdd998e67c18223fd4b6f0bfb74542bdc0b282d95776c5a27c8f8be7ab6` |

Normalization and the later template commit changed documentation only. The original extraction parent is `bd1fecb9`; the retained baseline binary remains applicable without rebuilding. Current `main` and `baseline` still contain the same product code, so incremental and cumulative product comparisons coincide for this candidate. Future acceptance into main does not automatically move baseline.

# Processing Flow

| Area | Baseline behavior | Candidate behavior | Expected effect |
| --- | --- | --- | --- |
| Masked alarm | Host callback remains queued | Guest `alarm_armed` state remains, host callback is canceled | Fewer masked timer callbacks/wakeups |
| Future deadline | Two truncating conversions can round early or to zero | Phase-aware two-stage ceilings | No early/same-time deadline for positive distance |
| Observation/acknowledgment | Pending state follows timer object | Elapsed guest state is reconciled explicitly | Preserve polled and reenabled interrupt behavior |
| Migration | No explicit armed field | v5 serializes it; v4 reconstructs supported state | Preserve compatible snapshots |

# Code Changes

- Preserve and reconcile `alarm_armed` independently from the host timer.
- Correct future-deadline arithmetic without collapsing the two guest-clock quantizations.
- Route clock changes and VMState restoration through the explicit timer state contract.
- Extend the existing PTIMER production translation-unit tests and baseline negative controls.

**Main code path:** NV2A PTIMER/PRAMDAC scheduling, interrupt state, and VMState.
**Commits:** [candidate head](https://github.com/Mainkill1/xemu/commit/8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b)

# Profiling

| Measurement | Stable baseline | Current candidate |
| --- | ---: | ---: |
| Exact timer failure controls | 5/5 intended failures | Matching repaired controls pass within 24/24 suite |
| PTIMER callbacks/wakeups in fixed work | Not measured | Not measured |
| Host CPU/GPU attribution | Not measured | Not measured |

**Bottleneck status:** Still testing. The source-level redundant callback is established; its measured host cost and the combined patch's fixed-work effect remain unknown.

# Performance Results

## Headline Results

| PGR2 cell | Mean interval, ms (baseline → candidate) | Improvement % | p95, ms (baseline → candidate) | Improvement % | p99, ms (baseline → candidate) | Improvement % |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Snapshot Vulkan | 34.484 → 34.627 | -0.42% | 40.910 → 41.338 | -1.05% | 45.186 → 46.296 | -2.46% |
| Snapshot OpenGL | 35.122 → 37.695 | -7.32% | 42.308 → 45.400 | -7.31% | 46.086 → 52.745 | -14.45% |
| Fresh start Vulkan | 33.333 → 33.343 | -0.03% | 33.412 → 33.554 | -0.42% | 34.497 → 34.341 | +0.45% |
| Fresh start OpenGL | 33.343 → 33.333 | +0.03% | 33.822 → 33.740 | +0.24% | 36.059 → 34.440 | +4.49% |

Improvement % is normalized so positive is good and negative is bad. These interval metrics are lower-is-better, using `100 × (baseline - candidate) / baseline`.

PGR2 uses one 60-second candidate capture per renderer/launch mode against the retained matching baseline cell, scale 1, identical seed/configuration and capture tools. Snapshot warmup is 3 seconds; fresh-start warmup is 30 seconds after pinned navigation. Guest display-write intervals are not rendered FPS. Start images show stationary race scenes and do not prove sustained driving progression. Host presents remain a separate metric.

| Earlier Morrowind observation | Vulkan baseline → candidate | OpenGL baseline → candidate |
| --- | ---: | ---: |
| Display-write cadence, per second | 23.723 → 24.632 | 32.798 → 34.254 |
| Interval p95, ms | 47.990 → 47.619 | 38.098 → 37.712 |
| Interval p99, ms | 57.134 → 55.640 | 42.848 → 41.896 |

Morrowind has one 20-second candidate cell per renderer against retained measurements from a different time. Both reached unpaused gameplay and passed image checks. Favorable observations do not establish causality or offset unfavorable PGR2 rows. Repeatable fixed-work performance and callback/wakeup attribution remain pending.

# xiso Results

**Scope:** Full baseline attempts; candidate not run
**Repeats:** Two baseline OpenGL setup/transport attempts
**Cases:** No valid performance suite. The latest attempt produced 149 PASS / 1 FAIL of 150 emitted records, while four xemu-only records were omitted.

| Gate | Status |
| --- | --- |
| Selected-plan opt-in | Source repair in [perf-tests PR #13](https://github.com/Mainkill1/xemu-perf-tests/pull/13); native 154-record validation pending |
| Output transport | Strict output-only repair in [perf-tests PR #14](https://github.com/Mainkill1/xemu-perf-tests/pull/14); native calibration pending |
| DMA report guard | Failing case tracked in [xemu #60](https://github.com/Mainkill1/xemu/issues/60) |

No failed attempt is used as a performance result or golden oracle.

# Correctness

| Check | Result and scope |
| --- | --- |
| Native production PTIMER controls | 24/24 passed, exit 0 |
| Shared generic timer target | 576/576 passed, exit 0 |
| Exact baseline negative controls | 5/5 intended assertions failed, exit 3; repaired counterparts pass |
| Morrowind GL/VK initial snapshot smoke | 2/2 candidate cells passed |
| VMState roundtrip | Candidate v5 gameplay roundtrip passes; final old-v4 reload reaches controller overlay on both baseline and candidate |
| PGR2 snapshot/fresh-start | 4/4 candidate runner functional/measurement gates complete; timings do not establish performance acceptance |
| Full XISO | Baseline attempts are failed evidence, not performance passes; independent DMA, selection and transport gates remain |

The final Morrowind reload produced zero display writes on both builds, with identical failure-image hashes. Baseline initial/roundtrip/final counts were 242/246/0; candidate counts were 243/244/0. [Issue #61](https://github.com/Mainkill1/xemu/issues/61) tracks that inherited readiness limitation. This does not establish a timer-specific regression, nor complete snapshot compatibility qualification.

| Check | OpenGL | Vulkan |
| --- | --- | --- |
| Targeted production timer tests | Pass — shared native suite | Pass — shared native suite |
| Functional PGR2 capture | Pass — Snapshot and FreshBoot runner gates | Pass — Snapshot and FreshBoot runner gates |
| Visual output | Pass for static scene/UI scope | Pass for static scene/UI scope |
| Guest progression | Not established — captures remain stationary | Not established — captures remain stationary |
| Vulkan validation | N/A for PGR2 production timing; final suite pending | Not run — full suite blocked |
| VMState old-v4 reload | Unresolved inherited controller overlay, reproduced on baseline | Unresolved inherited controller overlay, reproduced on baseline |

**Correctness result:** The candidate fixes its targeted native controls. Full snapshot compatibility and full-suite correctness remain incomplete.

# Resource Results

| Metric | OpenGL | Vulkan |
| --- | --- | --- |
| Host CPU | Not summarized from a comparable fixed window | Not summarized from a comparable fixed window |
| Host GPU | Raw sensor capture retained; no reviewed comparison | Raw sensor capture retained; no reviewed comparison |
| RAM / VRAM | Not collected | Not collected |
| Timer callbacks / wakeups | Not measured | Not measured |

No fixed-work callback/wakeup reduction or causal CPU/GPU/memory saving has been established. PGR2 resource observations, where available, retain their sensor and sampling limits in the linked report. Production timing and detailed diagnostic analysis remain separate. Extra work at timer observation/scheduling boundaries must be included in the acceptance comparison.

# Validation Status

| Test | OpenGL | Vulkan |
| --- | --- | --- |
| Targeted patch tests | Pass | Pass |
| Representative/partial xiso | Not run — transport qualification incomplete | Not run — transport qualification incomplete |
| Profiling comparison | Testing — fixed-work pending | Testing — fixed-work pending |
| Resource comparison | Not run — fixed-work attribution pending | Not run — fixed-work attribution pending |
| Morrowind snapshot | Pass for initial 20-second smoke; old-v4 progression unresolved | Pass for initial 20-second smoke; old-v4 progression unresolved |
| PGR2 snapshot | Regression observation — one non-interleaved pair | Regression observation — p99 above 2% in one pair |
| PGR2 fresh-start | Neutral observation — one pair | Neutral observation — one pair |
| Full xiso | Not run — independent gates remain | Not run — independent gates remain |
| Final visual validation | Not run — candidate is not ready | Not run — candidate is not ready |

# Tradeoffs / Regressions

**Performance regressions:** Snapshot OpenGL mean/p95/p99 and Vulkan p99 are unfavorable above 2% in one pair.
**Correctness regressions:** No candidate-specific regression established; old-v4 controller overlay remains unresolved on both builds.
**Resource tradeoffs:** Unknown; fixed-work callbacks, CPU, GPU, RAM, and VRAM are not qualified.
**Other concerns:** Single captures are non-interleaved and static; they cannot establish causation or sustained driving behavior.

# Decision

**Keep draft. Do not merge or advance baseline.** Fix the known defects and establish that the patch does not cause a performance regression above 2%, preserving individual workload and tail results. Next, qualify the strict fixed-work runner, compare the exact binaries on both renderers, and resolve compatibility and full-suite gates. Unfavorable or inconclusive evidence cannot authorize acceptance.

**Result:** Continue testing.
**Integration path:** Merge to `main` only after the exact candidate passes correctness and the fixed-work performance gate. Preserve its incremental result against previous `main` and cumulative result against `baseline`; move `baseline` only in a separate deliberate rebaseline decision.

**Follow-up:**

- [ ] Repair and independently approve the strict output-only runner contracts.
- [ ] Run one baseline-only calibration per renderer.
- [ ] Run the seeded fixed-work comparison on OpenGL and Vulkan.
- [ ] Measure PTIMER callback/wakeup and relevant host-resource changes.
- [ ] Resolve the old-v4 readiness limitation.
- [ ] Complete the full-XISO gates before final acceptance.

Full-suite blockers are independently tracked in [xemu #60](https://github.com/Mainkill1/xemu/issues/60), [perf-tests #10](https://github.com/Mainkill1/xemu-perf-tests/issues/10), and [perf-tests #11](https://github.com/Mainkill1/xemu-perf-tests/issues/11). The explicit test-selection repair is in [perf-tests PR #13](https://github.com/Mainkill1/xemu-perf-tests/pull/13); source review is not native full-suite acceptance.

# Evidence

[PGR2 retained-baseline/candidate comparison](https://github.com/Mainkill1/xemu-perf-tests/blob/b180091ccfc14d198426a0802b4cb5c9ad7153cc/docs/evidence/ptimer-main-20260909/pgr2/README.md) · [full-precision comparison data](https://github.com/Mainkill1/xemu-perf-tests/blob/b180091ccfc14d198426a0802b4cb5c9ad7153cc/docs/evidence/ptimer-main-20260909/pgr2/comparison.json)

[Native timer and Morrowind evidence](https://github.com/Mainkill1/xemu-perf-tests/blob/e49d8ef33d3aa6efa9722502ef5a6254a824b986/docs/evidence/ptimer-main-20260909/REPORT.md) · [retained baseline campaign](https://github.com/Mainkill1/xemu-perf-tests/blob/e49d8ef33d3aa6efa9722502ef5a6254a824b986/docs/evidence/baseline-campaign-20260909/REPORT.md) · [baseline diagnostic release with DWARF and matching source](https://github.com/Mainkill1/xemu/releases/tag/baseline-bd1fecb9-20260909) · [acceptance issue #40](https://github.com/Mainkill1/xemu/issues/40).

Earlier failed build dispatches, collector attempts, baseline controls and runtime evidence remain preserved in those reports. Historical S/Full-Speed or PR #48 tests qualify their recorded sources, not this candidate.

# Final Summary

**Status:** Testing

The patch fixes the targeted native timer controls, but it is not ready to merge. PGR2 FreshBoot was neutral in one capture pair, while Snapshot OpenGL and Vulkan tail observations crossed the 2% hold threshold. Strict fixed-work comparison, resource attribution, migration readiness, and full-XISO validation remain incomplete, so `main` and `baseline` stay unchanged.
