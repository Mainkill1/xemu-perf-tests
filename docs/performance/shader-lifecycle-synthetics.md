# Deterministic shader lifecycle synthetics

**Status: proposed test-suite design, not an implemented XISO or a measured optimization.**

Review date: 2026-09-24. Test repository base:
`bf8dbe70f12f4d97f59f3f8e14b04fe9a04bf0f9`. Renderer reference:
`134de6616e1d8f5bfe9d919a4e98e0ff7da3c928`. Related work:
[loading-stall report](https://github.com/Mainkill1/xemu/issues/198),
[renderer handoff](https://github.com/Mainkill1/xemu/pull/203), and its
[implementation research lanes](https://github.com/Mainkill1/xemu/pull/203).
Use the PR body for the current lane list; the owning issues are #204-#208.

## Decision

Build a deterministic **Xbox guest workload**, not a standalone host GLSL
benchmark, as the primary test. Drive the production NV2A -> shader translation
-> SPIR-V -> module -> full graphics pipeline -> draw path. Add a small,
opt-in renderer event stream for attribution. A guest checksum or guest timer
alone cannot tell which host executable drew the image.

Start with **eight workload families, twelve recipes each: 96 core recipes**.
Use eight recipes for smoke, the full corpus for qualification, and repeated
bursts for pressure. Add independent controls and 31/32/33 eligible-family
boundary probes. The number 96 is a bounded engineering starting point, not a
measured optimum or a claim of 96 distinct driver compilations.

The deliverable should answer:

- How long before the first correct workload image, with empty versus learned
  caches, and how much of that interval was shader/pipeline work?
- Was a complete fallback executable ready before demand? If not, which stage,
  pipeline state, admission decision, or queue prevented it?
- How long from demand to first **submitted draw using the specialized full
  pipeline**, and how much time was queueing, translation, driver work,
  publication, or waiting for the next matching draw?
- Did the fallback, transition, and specialized outputs agree with the same
  approved reference inputs? Did depth/stencil/report or texture dependencies
  also remain correct where the workload uses them?

This test PR must not change renderer defaults, repair the compiler, install a
new cache policy, or claim that synthetic coverage proves every game is fixed.

## Why these boundaries

The reviewed interpreter handles up to eight combiner stages, with texture
results supplied to it. More combiner descriptions do **not** necessarily mean
more fallback binaries. Vertex programs, texture-shell variants, optional
geometry, render targets, and other pipeline state remain relevant [S2].
The reviewed prewarm policy has a **32-candidate launch allowance**, not a
32-pipeline performance guarantee [S3]. This is why a five-shader loop is too
narrow and a hundred arbitrary constant changes are not a useful substitute.

Dolphin's hybrid design motivates comparing ready fallback rendering against
later specialized rendering, including pipeline variants [R1]. Epic separately
tracks shader-only, minimal, and full PSO coverage and distinguishes unpredicted
work from work queued too late [R2]. Vulkan explicitly separates modules from
pipelines; creation feedback is valid only when its VALID flag is set [R3-R5].
These are design inputs, not evidence about the performance of this fork.

A secondary, optional **captured full-pipeline replay** may isolate driver
compiler costs using Fossilize [R6]. It must remain a diagnostic companion: it
bypasses guest dispatch, xemu scheduling, and output validation, so it cannot
replace the XISO acceptance run.

## Corpus: legal, useful work rather than random bit patterns

The companion [matrix](shader-lifecycle-corpus.v1.json) is a **design manifest**.
It is not accepted by the existing runner and is deliberately outside
`resources/catalog.json`. Its Cartesian selectors expand to the following 96
candidate recipe IDs. Native registration occurs only after legal register
encodings, initialized dependencies, non-degenerate output, and output oracles
are implemented. Do not silently drop a candidate that fails those checks.

| Family / 12 recipes each | Structural recipe axes | What it targets |
| --- | --- | --- |
| `combiner-chain` | 1/2/4/8 stages x modulate/add/interpolate graphs | Specialized source growth; simple versus deep interpreter work |
| `combiner-mapping` | dot-AB/dot-CD/mux/blue-to-alpha x unsigned/signed/expand mapping | Register dependencies, alpha propagation, conditional paths |
| `texture-fanout` | 1/2/3/4 active stages x point-2D/linear-2D/point-cube | Texture-shell identity plus meaningful multi-texture evaluation |
| `dependent-texture` | dependent-AR/dependent-GB/dot-2D/dot-cube x three fixed coordinate fields | Dependent texture chains and unsupported-fallback attribution |
| `alpha-fog` | less/greater/greater-equal x disabled/linear/exp/exp2 fog | Fragment shell branches, discard and fog correctness |
| `vertex-program` | 8/32/64/128 encoded instructions x serial-MAD/dot-merge/reciprocal-mix | Translation and vertex compilation outside fragment fallback coverage |
| `fixed-function-lighting` | 1/4/8 lights x directional/point/spot/specular recipes | Generated transform-and-lighting vertex variants |
| `target-topology` | ARGB8888/RGB565 x triangles/lines/points x depth-off/depth-read-write | Complete pipeline/attachment coverage and optional geometry paths |

Each selector denotes an explicit allowlisted emitter template, **not arbitrary
register fuzzing**. For dependent chains, initialize each producer texture stage
before its consumer and specify stage dependencies in the emitted recipe. For
vertex programs, validate encoded slots, initialized registers, output position,
and termination against the pinned assembler/hardware contract; instruction
budgets include setup and epilogue. Reject an over-budget template rather than
truncating it. Mixed topology/attachment cases are coverage probes; use the
one-factor controls below for causal attribution.

Generate textures, vertices, constants, and lighting from a documented fixed
32-bit PRNG and seed. Use finite bounded inputs, positive reciprocal arguments,
visible gradients, and independent alpha/color signals. Every intended stage
must affect observed output. A long sequence that folds to a constant or
saturates every pixel to black is not a heavy compiler test. Retain emitted
register/microcode bytes, source hashes, SPIR-V hashes, normalized shader keys,
fallback-family keys, and full pipeline keys in diagnostic artifacts.

**Identity ledger:** count requested recipes, legal recipes, visible-output
recipes, normalized stage identities, fallback families, full pipelines, and
actual compile calls separately. Preserve many-to-one mappings. Byte-different
source, uniforms, guest state, and driver executable identity are not synonyms.
A source-hash alias is a result to investigate, not permission to manufacture
meaningless shaders until a nominal count is reached.

### Independent controls

| Control | Required observation |
| --- | --- |
| `identical-replay` | Exact same state/input sequence; no new xemu identities after settling |
| `uniform-only` | Change visible colors/constants without changing structural keys; output changes, shader identity does not |
| `pipeline-only` | Hold shader modules fixed; change one legal blend/depth/stencil state at a time; record full-pipeline identity and actual driver work |
| `fill-only` | Increase pixels/draws with already-ready executables; separate GPU load from compile stalls |
| `dependency-consumer` | Producer render-to-texture, depth/stencil consumer, and query/report checks expose missing side effects |

Controls are reported separately from the 96 recipes. Compilation caused by a
control is not automatically a bug: the ledger must show whether an application
key, full pipeline, or driver variant changed. Uniform-only structural misses,
however, require attribution before claiming the corpus measures new code.

## Ten scenarios using the same corpus

| ID | Deterministic work | Primary result |
| --- | --- | --- |
| `startup` | Fresh process, explicit empty or cloned learned cache set; first selected recipe without target warmup | Launch, renderer-ready, target first-demand, first-correct-output intervals |
| `first-use` | One recipe per fresh process for smoke/isolation; optionally all 96 individually | Single-cold-demand latency and missing-stage reason |
| `burst` | Reveal 1/8/32/96 selected recipes in one guest frame; four small draws per recipe | Foreground blocking, queue pressure, deduplication, first-use tails |
| `stream` | Reveal one new core recipe per frame for 96 frames; then reuse all recipes | Sustained arrival versus compiler service and demand promotion |
| `residency` | Reuse selected recipes for 240 fixed guest frames, four draws per active recipe per frame | Fallback residence, specialized readiness and first specialized submission |
| `warm-replay` | Replay exactly the same bytes in-process; separately restart from a cloned trained cache set | Resident reuse versus persisted reconstruction |
| `unseen-phase` | Warm variants 0-5 in each family (48 recipes); reveal variants 6-11 (48 recipes) | Genuine new-state behavior; prove host-key novelty rather than assuming it |
| `prewarm-boundary` | Fresh launches with 31/32/33 verified distinct eligible full-family records | Allowance boundary, missing-artifact accounting, fairness and ready-before-demand coverage |
| `contention` | Repeat the 96-recipe burst eight times while warmed visible work continues | Queue backpressure, duplicate admission, foreground versus worker contention |
| `lifecycle` | Controlled queue-full, delayed-worker, compile-error, generation-reset and shutdown cases | Terminal outcomes, cancellation, stale-result rejection and bounded progress |

Repeated pressure is **768 recipe demands, not 768 unique shaders**. The
prewarm-boundary denominator is verified eligible *family records*, not guest
recipe count. If the native corpus supplies fewer than 33, report
`coverage_insufficient`; add reviewed structural recipes rather than relabeling
uniform changes as families. Also sweep queue capacity C-1/C/C+1 using the
**reported current capacity**, not a hard-coded guess.

Use a small fixed render area for compile-focused runs. Separately use full
640x480 drawing and a fixed, documented overdraw multiplier for execution-cost
runs. Do not change pixels, work, or test duration adaptively between baseline
and candidate. A pilot may set a larger fixed work count for a later campaign;
that creates a new manifest identity. 240 unlocked guest frames is **not** a
promise of four wall-clock seconds.

Frames keep flowing because the reviewed prewarm service depends on renderer
service opportunities. Record flips/service opportunities and zero-opportunity
runs. Do not accidentally turn the burst into a per-draw GPU wait loop or warm
all target pipelines while drawing the test menu.

## Lifecycle telemetry and the actual handoff metric

Keep guest and host measurements separate. Host lifecycle timestamps come from
one monotonic host clock domain. Startup launcher durations use an explicitly
aligned host clock or remain separate fields; never subtract guest TSC ticks
from host times. Diagnostic event payloads must include:

```text
run_id, test_id, revision, case_id, phase_id, guest_frame, draw_sequence
renderer_generation, exact_shader_key, fallback_family_key, full_pipeline_key
request_id, worker_ticket, thread_id, event_sequence, host_monotonic_ns
route, readiness_class, result, reason
```

Use one immutable job identity across demand, work, and publication, including
shared jobs with multiple demanding cases. Record demand at the production
selector when the actual draw first requires that key, **not merely when a
case marker arrives**. A vCPU port write is not proof PGRAPH has consumed
preceding commands. Correlate case context at the decoded draw boundary using
an ordered guest/PGRAPH marker or an equivalent explicit sequence mapping;
verify marker order under an intentionally backed-up FIFO.

```text
first exact demand
  -> queue admission / promotion / deferral
  -> worker start
  -> source generation end
  -> SPIR-V compile/load end
  -> shader modules ready
  -> full pipeline creation end
  -> renderer-owned publication
  -> first matching draw submitted using specialized full pipeline
  -> corresponding GPU completion / correctness checkpoint
```

Source generation may currently precede queueing or execute on an owner thread.
Record actual spans and thread ownership instead of forcing this logical chain
onto an inaccurate event order. Capture start/end pairs for cache lookup,
source generation, SPIR-V build, reflection/module materialization, full
pipeline creation, locks/waits, and publication. Parent/child spans may overlap;
do not sum overlapping spans into wall time.

For demand timestamp D, queue admission Q, worker start W, pipeline completion
P, publication U and first specialized submitted draw S:

```text
demand_to_specialized_draw_ns = S - D       # user-visible handoff metric
queue_wait_ns                = W - Q
publication_delay_ns         = U - P
next_matching_draw_delay_ns  = S - U
fallback_residence_frames    = frames actually submitted with fallback
```

Store the raw events; derive only metrics whose endpoints exist and are in the
same generation/clock domain. A pipeline built before demand is a cache hit,
not a negative compile duration. Pipeline readiness, pipeline publication,
first binding, first submitted draw, and first GPU completion are different
milestones. A shader module that exists while a full pipeline is absent is
**not a completed transition**. A pipeline that is published but never used has
`first_specialized_draw=null`, not a zero-millisecond success.

For experimental pipeline-library work, additionally distinguish first usable
fast-linked pipeline from later optimized/LTO replacement. Do not rename the
first library object to a complete executable.

Readiness at first demand uses mutually exclusive classes:
`hit`, `missed`, `too_late`, `unsupported`, `queue_deferred`, or `failed`.
Keep specialized and fallback readiness classifications separately; specialization
can be late while a complete fallback hit still gives uninterrupted rendering.
Record suppression/omission as a separate draw outcome.

Add an event-stream header/version, capability bits, sequence numbers, a footer
with dropped-event count and completion status, and a bounded buffer. No
capability, truncated events, sequence gaps, overflow, or unresolved key joins
can produce a transition **pass**. Report `unsupported_telemetry` or
`incomplete_telemetry` while retaining ordinary guest observations. Trace
serialization/file I/O stays out of render hot paths; detailed spans are opt-in.

Vulkan creation feedback is optional attribution. Store its validity and units;
invalid or unsupported duration is `null`, never zero [R4]. Measure the host
call wall span too. An application pipeline-cache-hit feedback flag says
nothing definitive about hidden driver-cache coldness. Compile-forbidden
probing must follow the supported Vulkan feature contract [R5] and be reported
as a probe, not mixed with a real compile.

## Checksums that can actually find rendering regressions

**Do not hash only shader source, a constant clear, a final overlay, or the last
recipe.** Retain the repository's separate input/work/result checksums and
`framebuffer_fnv1a64` convention [S1]. SHA-256 identifies source/XISO/artifacts;
the output hash is computed from actual completed guest-visible pixels.

Use two explicit observation modes:

1. **Correctness:** run fixed input frames through forced-specialized/Wait,
   supported forced-fallback, and natural hybrid paths. A test-only worker gate
   can hold specialization publication for several frames, then release it,
   to ensure fallback, takeover, and post-takeover output are all exercised.
   Hold/release affects diagnostics only; it is forbidden in timing acceptance.
   Record each observed route, frame input hash, actual output hash, and oracle
   identity. Unsupported fallback is a visible skip, not specialized coverage
   masquerading as fallback. Save raw failing surfaces, not routine screenshots.
2. **Performance:** run without artificial delays or per-draw readbacks. Hash
   fixed workload checkpoints after measured intervals, and keep retained tiles
   or a bounded history surface so earlier recipes cannot disappear under the
   last draw. Record GPU completion time separately from readback/hash time.
   Qualify this exact build/corpus against the correctness mode; never describe
   sparse performance checkpoints as exhaustive transient-image validation.

Every case must run long enough in the fixed frame sequence to produce first,
fallback, first-specialized, and settled observations **when those routes occur**.
A too-fast natural transition is `fallback_not_observed`, not fallback parity.
A job not promoted within the configured frame budget is right-censored:
record elapsed lower bound and `transition_not_observed`. Do not add sleeps
until it passes, omit it from the denominator, or calculate percentiles only
from the surviving quick jobs without reporting the censored population.

### Pixel representation and reference policy

Hash active row bytes after the existing GPU-completion/readback protocol;
exclude pitch padding and UI. Metadata includes width, height, pitch policy,
format, channel order, sample/resolve policy, observation rectangle, and frame
input. For cross-format comparisons, use explicitly specified decoding rather
than comparing raw RGB565 bytes to ARGB8888 bytes. Compare only like scopes.
Depth/stencil and query/report observations have their own schema and oracles.

Use an independently derived known-answer check for simple control outputs.
For complex images, use a reviewed specialized/Wait regression baseline, pinned
to executable, backend, GPU/driver, scale, and arithmetic settings; preserve
oracle provenance. A stable current candidate must not approve its own golden.
Exact pixel hashes are required within the qualified environment. Cross-driver
or OpenGL/Vulkan floating-point differences require an explicit applicability
record and separately reported diagnostic pixel differences; do not silently
add a tolerance or erase low bits to turn a failure into a pass.

The validated history is an ordered sequence of
`(case_id, input_frame_id, observation_scope, actual_pixel_hash)`. Keep host route
metadata next to it, but do **not** mix route names or compile timing into the
image-parity hash: correct fallback and specialized output should compare equal.

### Mandatory falsification checks

Before using the suite to approve an optimization, prove it fails when one
observed pixel changes, an old frame is read, the wrong recipe is bound, a
uniform update is ignored, a workload is replaced by a clear, or an early frame
is bad but the final frame is correct. Independently prove telemetry rejects
module-only readiness, published-but-unused pipelines, missing/drop-count events,
misordered case markers, and stale-generation completions.

The optional **Continue/black** policy from #203 is a separate, deliberately
lossy experiment, not an accurate-rendering pass. Record omitted draws,
blackout duration, affected producer resources, progress, and eventual recovery.
Black frames must not satisfy the pixel oracle or count as rendered gameplay
throughput. A missing one-time render-to-texture producer cannot be declared
recovered merely because a shader finished building.

## Cache and experiment matrix

Record requested and effective Vulkan mode, shader-miss policy, restart state,
worker counts/priorities, renderer scale, arithmetic mode, instrumentation,
validation, and exact Release executable/hash/symbol identity. Keep
Off/Fallback/Prewarm/Always distinct; use existing cache policy ownership (#97),
not a new competing toggle. Current Always is not automatically a strict
no-prewarm control; prove effective behavior before interpreting it [S4].

| Cache treatment | Required controls |
| --- | --- |
| Application cold | Fresh process and isolated empty xemu history/SPIR-V/pipeline-cache namespace |
| Learned history, missing artifacts | Cloned history with intentionally absent stage artifacts; preserve exact missing-item manifest |
| Persisted warm | Same cleanly saved, hashed history/SPIR-V/pipeline-cache seed cloned before every A/B trial |
| Resident warm | Identical replay within the same process, separately labeled |
| Driver cold | Claim only when vendor-specific driver-cache isolation/reset is actually verified; otherwise `driver_cache=unknown` |

Never clear the user's ordinary shader cache, configuration, or HDD. Use a
private per-run environment and explicit test launch. Do not start tests just
because a config/artifact is uploaded. Do not use a GPU snapshot to claim cold
renderer initialization; that resumes past initialization.

For warm acceptance use five excluded warmups and at least fifteen measured
independent runs per condition, interleaved A/B or ABBA with matched cache seeds.
For a **cold** endpoint do not warm the target first: each measured observation
starts from its declared fresh process/cache state. Separate OS/host stabilization
from target shader warming. Fifteen runs can support a median/dispersion report;
accurate p99/p99.9 needs many more underlying observations. Always publish sample
counts, raw samples, p50/p95/p99 where supported, max, MAD, confidence intervals,
censored/failed counts, and hitch counts above 8.33/16.67/33.33/50/100 ms.

Frame hitches are not automatically shader stalls. Attribute compiler overlap,
foreground waits, submission/GPU waits, and service gaps independently. Avoid
double-counting overlapping compile intervals as total stalled wall time.
Unchanged work/hashes, lower time to first correct output, fewer/worse-tail
foreground stalls, completed specialization, and acceptable steady-state cost
are joint acceptance criteria. Average FPS or a faster pipeline function alone
is insufficient.

## Repository ownership and output

`xemu-perf-tests` owns generated guest recipes, stable catalog IDs, checksums,
configs, evidence validation, and compact reports. A **separate focused xemu PR**
owns production-linked lifecycle events/test-only scheduling gates. The guest
suite may run without that companion, but promotion timing is then explicitly
unavailable. This design PR does not implement either native side.

Extend the existing suite patterns, marker protocol, result store, catalog
source/generator, and runner artifact format [S1]. Do not grow
`game_load_composite_tests.cpp` into a shader laboratory. Proposed filenames and
red-first checks are in the [implementation plan](../superpowers/plans/2026-09-24-shader-lifecycle-synthetics.md).

Use `docs/evidence/pr-<number>/shader-lifecycle/<run-id>/` for committed summaries
and small proofs; keep large raw artifacts in durable release/run storage with
SHA-256 manifests. Retain failures. Required artifacts:

```text
manifest.json               # build/config/cache/oracle identities and effective state
resolved-cases.json          # exact expanded recipes and operation counts
shader-identities.json      # guest -> stage -> fallback-family -> full-pipeline mapping
lifecycle.jsonl             # bounded, sequenced raw host events and completeness footer
checkpoints.jsonl           # input scope, route, GPU completion, actual/expected hashes
guest-results.*             # byte-exact guest result files
summary.json / summary.csv  # compact derived metrics, denominators and gate results
failures/                   # raw failing pixels/state, errors, crashes, validation messages
```

Suggested compact row:

```text
case | cache | mode | eligible | first-use ms | ready-before-demand |
queue ms | pipeline ms | first-specialized ms/frame | fallback frames |
p99/max frame ms | hash | transition status | coverage reason
```

Unknown values remain null. Metrics contain no invented example measurements.

## Source map and primary references

[S1] Existing repository contract and extension points, reviewed at the test base:
[adding tests](https://github.com/Mainkill1/xemu-perf-tests/blob/bf8dbe70f12f4d97f59f3f8e14b04fe9a04bf0f9/docs/adding-tests.md),
[build registration](https://github.com/Mainkill1/xemu-perf-tests/blob/bf8dbe70f12f4d97f59f3f8e14b04fe9a04bf0f9/src/CMakeLists.txt),
[marker protocol](https://github.com/Mainkill1/xemu-perf-tests/blob/bf8dbe70f12f4d97f59f3f8e14b04fe9a04bf0f9/src/debug_output.h),
[suite API](https://github.com/Mainkill1/xemu-perf-tests/blob/bf8dbe70f12f4d97f59f3f8e14b04fe9a04bf0f9/src/tests/test_suite.h),
[existing pipeline controls](https://github.com/Mainkill1/xemu-perf-tests/blob/bf8dbe70f12f4d97f59f3f8e14b04fe9a04bf0f9/src/tests/pipeline_texture_switch_tests.cpp).

[S2] [Reviewed fragment interpreter](https://github.com/Mainkill1/xemu/blob/134de6616e1d8f5bfe9d919a4e98e0ff7da3c928/hw/xbox/nv2a/pgraph/glsl/psh-uber.c).

[S3] [Reviewed prewarm allowance and stage/result types](https://github.com/Mainkill1/xemu/blob/134de6616e1d8f5bfe9d919a4e98e0ff7da3c928/hw/xbox/nv2a/pgraph/vk/hybrid-prewarm.h).

[S4] [Source audit / mode and service boundaries](https://github.com/Mainkill1/xemu/blob/6bbd8316c6ff12639c5147315e5fe3738a55bcf4/docs/performance/issue-198-ubershader-loading.md).

[R1] [Dolphin: Ubershaders](https://dolphin-emu.org/blog/2017/07/30/ubershaders/).

[R2] [Epic: PSO precaching, validation and Hit/Missed/Too-late distinctions](https://dev.epicgames.com/documentation/unreal-engine/pso-precaching-for-unreal-engine).

[R3] [Khronos: shader modules](https://docs.vulkan.org/spec/latest/chapters/shaders.html) and [complete pipelines](https://docs.vulkan.org/spec/latest/chapters/pipelines.html).

[R4] [Khronos: valid pipeline creation feedback and nanosecond duration](https://docs.vulkan.org/refpages/latest/refpages/source/VkPipelineCreationFeedback.html).

[R5] [Khronos: compile-required pipeline creation flag](https://docs.vulkan.org/refpages/latest/refpages/source/VkPipelineCreateFlagBits.html).

[R6] [Valve: Fossilize object serialization and replay](https://github.com/ValveSoftware/Fossilize).
