# Shader Lifecycle Synthetics Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` or
> `superpowers:subagent-driven-development` to implement and review one task at
> a time. Checkboxes below are implementation gates, not completed work.

**Goal:** Reproducibly measure startup, first-demand stalls, fallback residence,
first specialized submission, and correct output from meaningful NV2A workloads.

**Architecture:** An Xbox guest suite drives production renderer paths. A focused
xemu companion adds optional lifecycle attribution. Host tooling joins sequenced
host events to guest observations; missing telemetry never becomes a fake pass.

**Tech stack:** Existing C++/NXDK/pbkit++ guest, Python standard-library host
contracts, current xemu Vulkan renderer, existing runner artifact transport.

**Spec:** [Design](../../performance/shader-lifecycle-synthetics.md) and
[design matrix](../../performance/shader-lifecycle-corpus.v1.json).

**State:** No native suite, renderer hook, report tool, or golden is implemented
by this design PR. Code below specifies interfaces and test expectations; it is
not a claim that these functions already exist. Keep the PR draft until native
implementation and qualification evidence are available.

## Global constraints

- Preserve defaults and Off/Fallback/Prewarm/Always; Wait is the reference.
- 96 planned recipes = eight families x twelve variants. Smoke = eight.
- 240 fixed residency guest frames; four draws per active recipe per frame.
- Pressure repeats 96 recipes eight times: 768 demands, not 768 new shaders.
- Use explicit legal templates; no copyrighted assets, random register fuzzing,
  silent skipped recipes, adaptive A/B work, or target warmup before cold timing.
- Separate output parity from route/timing metadata and from lossy Continue.
- Use isolated cache/HDD/config paths. Upload never launches a test by itself.
- No compile/pipeline timing claim without complete production-linked telemetry.
- No placeholder or candidate-generated goldens. Retain all failed observations.

## Review focus

Five particularly easy false passes, with owning tasks:

| Input or condition | Required behavior | Task |
| --- | --- | --- |
| Different guest recipes canonicalize to one host family | Show the alias; do not count multiple compilations | 1, 3 |
| FIFO backs up after a guest port marker | Case belongs to the decoded draw, not marker receipt time | 3 |
| Pipeline completes but no subsequent matching draw occurs | Report unobserved transition, not zero latency | 4 |
| Early wrong image is overwritten by a correct final image | Correctness history still fails | 2, 5 |
| Learned history exists but a stage artifact is missing | Separate missing artifact, attempted allowance, admission and demand outcome | 3, 6 |

## Ownership and independently reviewable slices

1. **Guest/corpus slice in xemu-perf-tests:** legal recipe builder, focused
   rendering, controls, input/output hashes, stable catalog registration.
2. **Telemetry slice in xemu:** draw/job/pipeline lifecycle events and diagnostic
   gates. Reference Mainkill1/xemu#198 and #203; do not combine shader repairs.
3. **Validation/campaign slice in xemu-perf-tests:** strict event joins,
   reference applicability, raw evidence and compact performance reports.

The guest slice can render and validate without the telemetry slice. It cannot
measure exact promotion until the companion capability is present. Do not fake
readiness based on FPS, image appearance, elapsed guest frames, or SPIR-V hits.

## Task 1: deterministic recipe inventory and narrow known-answer controls

**Files:** create `utils/shader_lifecycle_corpus.py`,
`tests/test_shader_lifecycle_corpus_contract.py`,
`src/tests/shader_lifecycle_recipes.h`, and
`src/tests/shader_lifecycle_recipes.cpp`. Consume the design matrix; keep raw
encoding logic in the C++ recipe builder, not duplicated as opaque JSON words.

**Interfaces:** Python `expand_design(document: dict) -> list[dict]` returns
ordered objects with `case_id`, `family`, `variant`, `selectors`, and `seed_u32`.
C++ `BuildShaderLifecycleRecipe(family, variant, seed)` produces owned generated
texture/microcode/register/input bytes plus an explicit legal/invalid result.
The template validator rejects uninitialized reads and illegal producer chains.

- [ ] Write red-first contracts for exact IDs/counts, axis order, unique
  selectors, fixed PRNG vectors, 32-bit wrap, serialization, and no implicit
  host-endian/padding bytes. Pin these expansion expectations:

```python
rows = expand_design(document)
assert len(rows) == 96
assert len({row['case_id'] for row in rows}) == 96
assert rows[0]['case_id'] == 'shader.lifecycle.combiner-chain.v00'
assert rows[11]['selectors'] == {'stages': 8, 'graph': 'interpolate'}
assert rows[-1]['selectors'] == {
    'color_format': 'rgb565', 'primitive': 'points', 'depth': 'read-write'}
```

- [ ] Implement the allowlisted templates, starting with one simple combiner
  and one vertex program plus independent input/output known answers. For
  example, byte serialization must be explicit:

```cpp
// Serialize one generated input word to the input-hash stream.
for (unsigned byte = 0; byte != 4; ++byte) {
    const uint8_t value = static_cast<uint8_t>(word >> (8 * byte));
    hash = (hash ^ value) * 1099511628211ULL;
}
```

- [ ] Expand family by family; test vertex instruction budgets including
  setup/termination, zero denominators, dependency initialization, alpha
  liveness, signed mappings, and target-format legality. A rejected family
  blocks its advertised native coverage instead of shrinking expected counts.
- [ ] Verify that each recipe produces a non-degenerate observable output.
  Host identity uniqueness belongs to Task 3; do not assert 96 unique shaders
  from 96 different recipe labels.
- [ ] Run `python3 -m unittest discover -s tests -p
  'test_shader_lifecycle_corpus_contract.py'`, build the guest, retain the
  first independent KAT proof, and commit this slice.

## Task 2: guest rendering, fixed phases, and real output observations

**Files:** create `src/tests/shader_lifecycle_tests.h/.cpp`; modify
`src/CMakeLists.txt`, `src/test_driver.cpp`, `src/runtime_config.h/.cpp`,
`src/result_store.h/.cpp`, and `utils/test_catalog.py` only where the existing
registration/config/result interface requires it. Reuse the actual host/suite
APIs rather than copying a second profiler. Add
`tests/test_shader_lifecycle_guest_contract.py`.

**Native catalog contract:** suite `ShaderLifecycle`; eight family leaves
named `shader.lifecycle.<family>` plus the five named controls. Each selected
leaf emits exactly one existing-style leaf result and keyed per-case
observations. Recipe IDs are child observations, not fake group timings.
Scenarios and recipe subsets are explicit resolved configuration, included in
comparison identity. Host-only startup/cache treatments and renderer lifecycle
fault tests must not be advertised as executable Xbox catalog leaves.
Regenerate rather than manually editing generated catalog files.

**Interfaces:** `DrawShaderLifecycleRecipe(TestHost&, const Recipe&, frame)`
submits initialized legal GPU work. `CaptureShaderLifecycleCheckpoint` is a
post-completion observer with case/input/scope/actual hash. These new helpers
must use the same recipe/input objects; no second random input generation.

- [ ] Write red-first tests that every advertised leaf is registered, selected
  case counts agree with emissions, cold mode has zero target warmup, and
  repeated pressure changes demand count rather than unique-recipe count.
- [ ] Implement fixed frame loops and preallocated input/scratch storage.
  A conceptual timing boundary using existing APIs is:

```cpp
EmitXemuPerfMarker(kXemuPerfMarkerMeasureBegin);
DrawShaderLifecycleRecipe(host_, recipe, frame_index);
host_.WaitForGpu();  // Completion is part of this end-to-end sample.
EmitXemuPerfMarker(kXemuPerfMarkerMeasureEnd);
// Readback and CPU hash are outside the measured sample.
CaptureShaderLifecycleCheckpoint(host_, recipe, frame_index);
```

  That is a **single-case isolation sample**, not the burst implementation.
  Burst/stream variants submit all scheduled draws before their declared
  phase-completion wait. Never add a GPU wait per draw in burst mode. Keep
  completion policy explicit in emitted data; do not compare submit-only
  samples to submit-plus-completion samples.
- [ ] Use separate retained tiles/history for earlier recipe observations, or
  explicit per-frame correctness captures. Hash shader-produced content before
  test text/clears. Add a control where an early wrong frame followed by a good
  frame still fails the observation sequence.
- [ ] Implement deterministic producer-consumer checks for render-to-texture,
  depth/stencil and reports where exercised. The existing `PipelineTextureSwitch`
  suite shows source KATs and completion/readback patterns; reuse its conventions
  rather than treating its final display color as this suite's shader oracle.
- [ ] Preserve current extended marker framing. Do not steal assertion IDs or
  assume that the existing vCPU marker receipt identifies a PGRAPH draw. The
  companion Task 3 owns the ordering/capability handshake.
- [ ] Run focused host contracts, catalog generation/check, Release build,
  then one focused leaf and its control with approved references. Commit.

## Task 3: production-linked lifecycle telemetry in a separate xemu PR

**Files in xemu:** modify `hw/xbox/nv2a/pgraph/vk/draw.c`, `shaders.c`,
`hybrid-prewarm.c`, and `renderer.c` at their actual ownership boundaries.
Create `hw/xbox/nv2a/pgraph/vk/shader-lifecycle.h/.c` for bounded event storage
and `tests/unit/test-shader-lifecycle.c` for production-linked contracts.
Wire the existing performance-event receiver after locating its current
implementation through the `0xE9`/extended-event definitions; do not create a
second incompatible receiver. Recheck current main before editing.

**Interfaces:** `ShaderLifecycleEvent` contains the exact identity/timestamps
specified in the design. `shader_lifecycle_emit(event)` writes only to bounded
in-memory storage when enabled. Export/drain runs outside hot timing paths.
Diagnostic queue gates are capability-advertised, disabled by default, and
recorded in the event header; performance acceptance rejects enabled gates.

- [ ] Write unit tests for module-ready/full-pipeline-missing, generation reuse,
  duplicate demands sharing one job, queue rejection, delayed publication,
  missing-artifact prewarm attempts, ordered PGRAPH case markers, buffer overflow,
  and shader job completion during shutdown. Use the actual selector/worker
  data paths, not a detached toy state machine.
- [ ] Emit `demand` in the real draw selector before a ready probe can create
  work. Emit queue admission/promotion, worker start/end, actual span thread,
  module readiness, complete pipeline creation, owner publication, and the
  first **submitted** specialized draw. Preserve the original behavior.
- [ ] Set `first_specialized_draw` only when generation and exact pipeline
  identity match and submission actually occurs. A successful lookup or bind
  without a draw is insufficient. Shader/family/pipeline IDs stay distinct.
- [ ] Prove case ordering with a deliberately backed-up FIFO and interleaved
  worker completions. A host CPU port marker arriving early must not reassign
  earlier queued draws to the new case. Include a PGRAPH-consumption anchor.
- [ ] Add optional Vulkan feedback only when supported and valid. Preserve
  invalid values as absent, even if a driver leaves a duration field unchanged.
- [ ] Add bounded diagnostic delayed-worker/generation-reset/failure controls.
  A control cannot silently remain active in normal gameplay or acceptance runs.
- [ ] Run focused production-linked native unit tests, exact Release builds,
  existing renderer regression gates and an instrumentation-off control. Publish
  this companion independently; no scheduler, cache, or default change belongs
  in its first commit.

## Task 4: strict host joiner and token-friendly report

**Files in xemu-perf-tests:** create `utils/shader_lifecycle_report.py` and
`tests/test_shader_lifecycle_report_contract.py`. Integrate through the existing
runner's artifact transport, not a second launcher or an assumed live connection
from the Xbox guest. Read original guest artifacts without rewriting them.

**Interfaces:** `summarize_run(manifest, events, checkpoints) -> dict` emits
summary rows and explicit gate failures. Input parsers enforce version, types,
identity, event completeness, same-clock timestamps and reference applicability.
CLI accepts explicit artifact paths and exits nonzero on an invalid gate; it
does not launch xemu, delete caches, or approve an oracle.

- [ ] Write fixture tests before implementation. At minimum:

```text
D=100, Q=110, W=150, P=240, U=270, S=300 (same clock/generation)
  -> demand_to_specialized_draw_ns=200
  -> queue_wait_ns=40
  -> publication_delay_ns=30
  -> next_matching_draw_delay_ns=30

D=100, module_ready=120, no pipeline or submitted draw
  -> transition_not_observed; duration=null

D=100, P=120, U=130, no subsequent matching draw
  -> transition_not_observed; duration=null

Ready pipeline used at first demand
  -> hit; no invented compile duration

Old generation publishes at 140; new generation demands at 150
  -> old publication cannot satisfy the new request

Missing footer, dropped_events>0, duplicate sequence, unresolved key
  -> incomplete_telemetry; cannot pass transition gate
```

- [ ] Implement joins by immutable request/key/generation, not nearest timestamp
  or worker index. Support shared jobs and cache hits, allow legitimate
  pre-demand preparation, and reject impossible intra-span endpoint order.
- [ ] Implement separate pixel gate and transition gate. Equality of two
  candidate-run hashes without an approved oracle does not pass either
  correctness qualification or oracle applicability.
- [ ] Report every requested case, including failures, unsupported routes,
  insufficient coverage, and right-censored transitions. Publish raw events and
  never replace unknown values with zero. Quantiles include explicit sample
  counts and report censoring separately rather than hiding slow incompletions.
- [ ] Run fixture contracts and validate one real native sample against manual
  source-boundary inspection before trusting reports. Commit with tiny synthetic
  fixture files labeled as fixtures, not measured performance evidence.

## Task 5: force the checker to catch wrong rendering and handoff errors

**Files:** add native test configs using the existing configuration format,
`tests/test_shader_lifecycle_oracle_contract.py`, and a reviewed oracle
applicability manifest under the repository's existing evidence conventions.
Do not put a made-up expected pixel hash in the design matrix.

- [ ] Derive narrow control KATs independently. Capture a pinned
  specialized/Wait reference for complex scenes; record GPU/driver/backend,
  scale, arithmetic mode, XISO/executable hashes and reviewer provenance.
- [ ] Run supported forced-fallback, specialized, and natural-hybrid recipes
  against the same input frames. Use the diagnostic worker gate only for
  coverage of fallback and transition; preserve the natural timing campaign.
- [ ] Demonstrate failures for altered pixel, ignored uniform, wrong shader,
  stale surface, replacement clear, and early-bad/final-good images. Demonstrate
  trace failures from Task 4 while the image remains correct.
- [ ] Keep unsupported cases visible. Compare OpenGL/Vulkan and 1x/4x where the
  path is sensitive, but use explicit oracle applicability rather than assuming
  bit-identical floating-point output across all environments.
- [ ] Run Continue/black separately when implemented. Omission is never accurate
  output, and dependent resources cannot be considered recovered solely on
  compiler completion. Report progress, omissions and remaining side effects.
- [ ] Retain original bad samples even after a successful retry. Commit oracle
  provenance and small proofs; store raw native artifacts by hash.

## Task 6: controlled campaign, evidence, and release gate

**Files:** update README/catalog descriptions after registration;
write summaries under `docs/evidence/pr-<number>/shader-lifecycle/` with manifests
pointing to durable raw artifacts. Keep results beside the test implementation
rather than burying the only evidence in PR comments.

- [ ] Inspect exact compiled feature/mode state and warm one isolated cache seed
  per environment. Clone that seed per independent run; do not warm A's cache
  and hand the modified directory to B. Record history, artifacts, pipeline
  cache and driver-cache knowledge independently.
- [ ] Run first-use smoke before the 96-case campaign. Confirm normalized key
  diversity, visible work, and no accidental menu/setup target warming.
- [ ] Exercise 31/32/33 eligible full-family records, missing-artifact attempts,
  few/no prewarm service opportunities, and actual queue C-1/C/C+1 pressure.
  Fail the intended coverage gate if the corpus cannot supply the denominator.
- [ ] Run warm acceptance with five excluded warmups and at least fifteen
  interleaved independent measured runs per condition. Cold endpoints use fresh
  declared state and no target warmup. Preserve all raw observations and report
  uncertainty, counts, max/tail stalls, dropped work and censored transitions.
- [ ] Compare current-main control, candidate-disabled and candidate-enabled
  with identical guest work. Use native low-overhead timing captures separately
  from detailed instrumentation and Vulkan-validation captures.
- [ ] Require correct observed pixels/dependencies, real fallback coverage,
  genuine specialized submission, bounded queue/lifecycle behavior, and a
  defensible end-to-end improvement before recommending a renderer patch.
  This suite's existence alone cannot close xemu#198.

### Existing build/catalog commands (not run by this design PR)

After the implementation files are present and the pinned submodules/toolchain
are available, use the repository's documented workflow:

```sh
python3 utils/test_catalog.py
python3 utils/test_catalog.py --check
python3 -m unittest discover -s tests -p 'test_*contract.py'
export NXDK_DIR="$PWD/third_party/nxdk"
cmake -B build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_TOOLCHAIN_FILE="$NXDK_DIR/share/toolchain-nxdk.cmake"
cmake --build build --parallel
# Expected image from the current workflow:
# build/src/xiso/xemu-perf-tests_xiso/xemu-perf-tests_xiso.iso
```

The design JSON is **not** a runtime config. Native launch commands must come
from the actual resolved runner/config schema after implementation; no fictional
`--shader-lifecycle` xemu switch is introduced here. Test execution remains an
explicit requested action, not an upload side effect.

## Draft-to-ready evidence checklist

- [ ] Legal guest emitters, catalog registration and focused native build pass.
- [ ] All enabled recipes have input/output observations and applicability.
- [ ] Production-linked lifecycle tests and companion capability pass.
- [ ] Altered rendering and faulty telemetry both fail for the intended reason.
- [ ] Cold/warm and 31/32/33 coverage are independently demonstrated.
- [ ] Complete raw artifacts and compact reports are retained by exact identity.
- [ ] No defaults changed, no user cache deleted, no performance claim inferred
  from a documentation/contract check or a CI build alone.
