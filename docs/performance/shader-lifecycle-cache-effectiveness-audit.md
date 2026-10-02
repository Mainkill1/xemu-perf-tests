# Shader lifecycle design audit: cache control and effectiveness

**Status: mandatory correction and qualification gate for PR #43.**

Review date: 2026-09-24. This audit rechecked the design against xemu at
`134de6616e1d8f5bfe9d919a4e98e0ff7da3c928`, the xemu-perf-tests base at
`bf8dbe70f12f4d97f59f3f8e14b04fe9a04bf0f9`, and the current Vulkan cache
control interfaces. It does not claim that native shader tests, renderer
telemetry, GPU oracles, or performance measurements exist.

This document is authoritative where it narrows or corrects
[the initial design](shader-lifecycle-synthetics.md) and
[implementation plan](../superpowers/plans/2026-09-24-shader-lifecycle-synthetics.md).
In particular:

1. An empty xemu cache directory does **not** prove a driver-cold pipeline.
2. Ninety-six guest recipes do **not** imply ninety-six distinct shaders,
   fallback families, graphics pipelines, or driver compilations.
3. The live fallback-family/pipeline-job capacities and the prewarm launch
   allowance are separate boundaries and must be tested separately.
4. The 96-recipe matrix is a candidate pool. The accepted v1 benchmark corpus
   is selected only after a native identity and sensitivity pilot.

## Audit findings

### 1. Current xemu has four distinct reusable-work layers

| Layer | Current mechanism | How a qualification run controls it |
| --- | --- | --- |
| Resident xemu objects | `ShaderBinding`, `ShaderModuleInfo`, and the 2,048-entry `PipelineBinding` LRU | Fresh process/device for cold endpoints; exact-key resident replay is a separate warm endpoint |
| xemu persistent artifacts | Learned fallback-family history and SPIR-V/shader artifacts under the xemu base path | Private per-run base path; empty, cloned, or intentionally incomplete manifests; never modify the user's cache |
| Application Vulkan pipeline cache | Serialized `VkPipelineCache`, restored by vendor/device/cache UUID and passed to `vkCreateGraphicsPipelines` | Add diagnostic `normal`, `empty`, and `null` modes; `null` must pass `VK_NULL_HANDLE`, not merely create an empty cache |
| Driver-internal cache | Implementation-managed memory/disk/precompiled pipeline data outside xemu's cache file | Disable only when the implementation advertises portable internal-cache control; otherwise record the state as natural or unknown |

The audited renderer creates a `VkPipelineCache` even when its initial data is
empty and passes that object to synchronous and asynchronous graphics-pipeline
creation. That empty object can accumulate reusable data during the process.
Therefore, deleting xemu's serialized cache is insufficient for a strict
application-cache-disabled run.

The driver-internal cache is a separate mechanism. Deleting xemu files,
changing xemu's base path, or passing an empty `VkPipelineCache` cannot prove
that the driver has no reusable compiler result.

### 2. The ubershader intentionally collapses combiner identities

For the ubershader route, xemu canonicalizes the combiner-control, RGB/alpha
input/output, and final-combiner fields before constructing the full pipeline
key. This is the intended benefit: many specialized fragment-combiner programs
can execute through one compatible fallback family.

Consequences for the synthetic corpus:

- `combiner-chain` and `combiner-mapping` are valuable specialization and
  takeover tests.
- They must **not** be counted as distinct fallback families merely because the
  guest recipe or specialized fragment source differs.
- The 31/32/33 prewarm-boundary test cannot be populated from recipe names. It
  needs 31/32/33 serialized, replay-safe, distinct eligible family records.
- A many-to-one mapping from specialized shader keys to one fallback-family key
  is an expected and useful result, not a failed test.

### 3. There are two independent capacity boundaries

At the audited renderer revision:

- `PGRAPH_VK_HYBRID_MAX_PIPELINE_JOBS` is 16.
- `PGRAPH_VK_HYBRID_MAX_FALLBACK_FAMILIES` is 16.
- `PGRAPH_VK_HYBRID_PREWARM_MAX_CANDIDATES` is 32 per launch.

The implementation must read and report the compiled capacities rather than
assuming those values remain current. Qualification then exercises:

```text
live request/job capacity: C-1 / C / C+1
prewarm launch allowance:  31 / 32 / 33 verified eligible family records
```

Queue saturation, fallback-family request saturation, and launch-candidate
exhaustion need separate result fields. One must not be used as evidence for
another.

## Driver-cache qualification

### Preferred portable control

When `VK_KHR_pipeline_binary` is supported, query
`VkPhysicalDevicePipelineBinaryPropertiesKHR` before device creation. Record at
least:

```text
pipelineBinaryInternalCache
pipelineBinaryInternalCacheControl
pipelineBinaryPrecompiledInternalCache
pipelineBinaryPrefersInternalCache
```

If `pipelineBinaryInternalCacheControl` is `VK_TRUE`, a compiler-isolation run
may chain this structure into `VkDeviceCreateInfo`:

```c
VkDevicePipelineBinaryInternalCacheControlKHR internal_cache = {
    .sType =
        VK_STRUCTURE_TYPE_DEVICE_PIPELINE_BINARY_INTERNAL_CACHE_CONTROL_KHR,
    .disableInternalCache = VK_TRUE,
};
```

The extension must be explicitly supported and enabled, and the diagnostic
mode must be recorded in the manifest. This is an opt-in benchmark control;
it must not change ordinary xemu defaults.

The run may be labeled `driver_internal_cache_disabled_verified` only when all
of the following are true:

1. `VK_KHR_pipeline_binary` was enabled on the selected physical device.
2. `pipelineBinaryInternalCacheControl` was reported true.
3. `VkDevicePipelineBinaryInternalCacheControlKHR.disableInternalCache` was
   supplied as true when the measured logical device was created.
4. The application pipeline cache mode was also recorded.
5. The event header confirms the effective state rather than only the requested
   state.

If the property is unsupported, the run is **not** portable driver-cold.

### Application pipeline cache control

Add one helper used by every production pipeline-creation path:

```c
static VkPipelineCache measured_pipeline_cache(PGRAPHVkState *r)
{
    return r->shader_lifecycle_app_cache_disabled
               ? VK_NULL_HANDLE
               : r->vk_pipeline_cache;
}
```

The exact implementation can differ, but synchronous construction, hybrid
workers, fallback construction, prewarm, and any pipeline-library experiment
must all use the same effective mode. A run cannot claim `app_cache=null` if one
creation path still receives `r->vk_pipeline_cache`.

Use three explicit application-cache treatments:

| Label | Initial state | Pipeline creation handle | Meaning |
| --- | --- | --- | --- |
| `app_cache_normal` | Restored xemu cache when eligible | xemu `VkPipelineCache` | Real user path |
| `app_cache_empty` | Empty cache object | xemu `VkPipelineCache` | No persisted seed, but in-process application reuse remains possible |
| `app_cache_null` | No application cache for measured creates | `VK_NULL_HANDLE` | Application pipeline caching disabled for those calls |

### Compile-required probe

Where `VK_EXT_pipeline_creation_cache_control` or equivalent core functionality
is supported, make a separate ready-only probe using
`VK_PIPELINE_CREATE_FAIL_ON_PIPELINE_COMPILE_REQUIRED_BIT`.

```text
VK_SUCCESS
    complete pipeline could be returned without compilation at probe time

VK_PIPELINE_COMPILE_REQUIRED
    the implementation would need compilation; returned pipeline is null
```

The probe is not the measured compilation. If it returns compile-required, make
the real creation call without the fail flag and time that call. If it returns a
usable pipeline, classify the demand as ready and retain or destroy the returned
object according to the diagnostic policy; do not immediately create it again
and call the second invocation a cold compile.

Record probe result separately from xemu's own module/pipeline cache lookups.
This tells us whether compilation was required **at that moment**. It does not,
by itself, prove that the driver had never seen the shader before.

### Pipeline creation feedback

Chain `VkPipelineCreationFeedbackCreateInfo` where supported. Preserve:

```text
feedback_valid
feedback_duration_ns
application_pipeline_cache_hit
per-stage feedback, when supplied
host-call wall duration
```

Only consume the duration when `VK_PIPELINE_CREATION_FEEDBACK_VALID_BIT` is set.
`APPLICATION_PIPELINE_CACHE_HIT` refers to the `VkPipelineCache` supplied by the
application; it is not proof that an implementation-internal cache missed.

### Mesa and vendor controls

On Mesa, `MESA_SHADER_CACHE_DISABLE=1` disables Mesa's on-disk shader cache and
is useful for a Linux diagnostic campaign. It does not replace a fresh process
or prove that every in-memory compiler reuse mechanism is disabled. Record it
as `mesa_disk_cache_disabled=true`, not as portable driver-cold.

Do not delete undocumented NVIDIA, AMD, Intel, Windows, or operating-system
cache directories on a user's normal system. A vendor-specific cold claim needs
vendor documentation plus an isolated test image or disposable machine. Without
that evidence, use one of these labels:

- `driver_natural_unseen_key`: fresh process/device, no prior use by this
  campaign, compile-required probe recorded, but internal cache not disabled.
- `driver_cache_unknown`: the implementation's internal state cannot be
  established.

A fresh exact key is preferable to deleting undocumented cache files, but it is
still not equivalent to verified driver-cold because an implementation can have
pre-populated or cross-process internal data.

## Revised experiment classes

Do not force one cache treatment to answer every question.

### A. Compiler-isolation campaign

Purpose: measure translation, SPIR-V work, module creation, driver pipeline
compilation, queueing, and publication without application or internal cache
reuse where portable controls exist.

Required state:

```text
fresh process and VkDevice
private empty xemu artifact namespace
app_cache_null
internal cache disabled and verified, when supported
one first demand per exact key
compile-required probe and creation feedback recorded
```

If internal-cache control is unavailable, the nearest substitute is
`driver_natural_unseen_key`; the report must not relabel it as driver-cold.

### B. Real-user cold/warm campaign

Purpose: measure the behavior users actually receive.

Required state:

```text
normal driver behavior
app_cache_normal
explicit empty/cloned xemu artifact namespace
cold first launch, clean persisted warm launch, and resident replay separated
identical fixed guest work and cache seed per A/B comparison
```

This campaign decides whether a proposed xemu change reduces practical hitching.
The compiler-isolation campaign explains where the work moved.

### C. Correctness and route-coverage campaign

Purpose: prove fallback output, specialized output, and transition behavior.
Diagnostic worker holds/failpoints may force otherwise rare routes. These runs
cannot make performance claims.

## Native effectiveness pilot

The initial 96 entries are a **candidate pool**. Implement and run a pilot before
committing to all 96 as the default qualification workload.

### Gate 1: legal and live guest work

For every candidate admitted to the benchmark:

- register/microcode encodings pass the existing replay-safety and native
  validation rules;
- all reads have initialized producers;
- finite, bounded inputs avoid accidental NaN/divide-by-zero behavior;
- the intended operation affects an observed pixel or dependency result;
- mutating or disabling that operation changes the expected observation;
- output does not collapse to the same saturated/cleared image for unrelated
  recipes.

A recipe that is legal but has dead output is a diagnostic fixture, not a heavy
shader benchmark.

### Gate 2: identity census

Run the eight-case smoke set with lifecycle telemetry and preserve the complete
mapping:

```text
guest recipe
  -> normalized vertex/geometry/fragment module keys
  -> specialized full PipelineKey
  -> fallback-family key, when supported
  -> fallback full PipelineKey
  -> compile-required probe outcome
  -> actual pipeline creation call(s)
```

Each axis has an expected identity layer:

| Change | Expected structural effect |
| --- | --- |
| Uniform-only | Pixels may change; module and full-pipeline structural keys do not |
| Combiner-only | Specialized fragment/module identity changes; fallback combiner fields may canonicalize to the same family |
| Vertex program or fixed-function recipe | Vertex module identity changes; full pipeline changes |
| Fragment shell/texture mode | Fragment shell and possibly fallback family change |
| Blend/depth/stencil or render-pass format | Full pipeline changes; stage module identities should remain fixed in the one-factor control |
| Fill-only | Draw/GPU cost changes; no new shader or pipeline identity |
| Exact replay | No new xemu identity after the first ready instance |

Unexpected aliases or unexpected new keys fail attribution. They are not hidden
by increasing the recipe count.

### Gate 3: identity-selected packs

Freeze multiple fixed packs after the census rather than treating one number as
all kinds of coverage:

1. **Smoke pack:** eight legal/live cases, one per family.
2. **Specialization pack:** distinct specialized stage/full-pipeline identities
   spanning shallow/deep vertex and fragment work.
3. **Fallback sharing pack:** multiple specialized combiner programs proven to
   use the same compatible fallback family, validating takeover and reuse.
4. **Fallback-family boundary pack:** 31/32/33 replay-safe, distinct eligible
   family records, generated from fields that survive ubershader
   canonicalization.
5. **Live-capacity pack:** C-1/C/C+1 distinct requests/jobs using the compiled
   capacity reported by xemu.
6. **Pipeline-only pack:** fixed stage modules with distinct full-pipeline state.
7. **Execution control:** fixed ready pipelines with increased pixel/draw load
   and no compile-required result.

The candidate pool can remain 96, grow, or shrink. The checked-in v1 packs must
be immutable and explicitly list their resolved identities. Runtime adaptive
selection is forbidden in A/B comparisons.

### Gate 4: prove that the measurement system has signal

Before interpreting an optimization, run diagnostic calibration faults at
known ownership points, for example:

```text
+10 ms and +25 ms source/SPIR-V worker delay
+10 ms and +25 ms pipeline-build delay
+10 ms and +25 ms renderer-publication delay
forced queue-full and one stale-generation completion
```

For each injected delay, the matching lifecycle span must move in the expected
direction, the end-to-end handoff interval must reflect the delay when it lies
on the critical path, and unrelated spans must not absorb the attribution. Use
predeclared error bounds based on host timer resolution and scheduling noise.
At minimum, the confidence interval for the measured shift must exclude zero
and the attributed median shift must retain most of the injected delay.

These are diagnostic calibration runs, not candidate performance results.

### Gate 5: prove fallback-to-specialized correctness

For supported cases:

- force fallback residence in a correctness-only run;
- hash actual completed pixels/dependencies during fallback;
- release specialization and identify the first submitted specialized draw;
- hash first-specialized and settled results;
- compare all like-scoped observations with approved oracles;
- prove that an early bad frame followed by a good final frame still fails.

A specialized pipeline that is built but never submitted is a censored
transition. A black/omitted draw belongs to the separate lossy policy and cannot
pass the accurate-output oracle.

### Gate 6: compare the corpus with real renderer states

Synthetic tests need not reproduce game assets or timing, but they must exercise
the same production state dimensions. Collect structural telemetry from a small
set of real-title reproductions:

```text
normalized module-key field buckets
fragment route and rejection reason
fallback-family and full-pipeline key hashes
vertex-program lengths and fixed-function features
texture shell modes, topology, attachment formats, depth/stencil state
queue/admission/readiness class and pipeline creation duration bucket
```

Store only state/key summaries and counts; retail assets are not required. The
qualification report compares the real trace buckets with the synthetic packs
and identifies uncovered buckets. Add a synthetic recipe only when it closes a
specific uncovered production state or a required boundary/negative control.

A synthetic suite is effective when it both covers the intended code paths and
responds to controlled changes in those paths. Similar-looking images or a large
shader count are not evidence of representativeness.

### Gate 7: repeatability and decision threshold

For each accepted pack:

- retain every raw run, failure, timeout, and censored transition;
- use fresh declared cache state for each cold endpoint;
- use interleaved A/B or counterbalanced identity banks;
- report median, MAD, tails, sample count, and confidence intervals;
- record compile-required, queueing, fallback residence, publication, first
  specialized submission, and steady-state execution separately;
- reject a performance claim when observed improvement is smaller than the
  pilot's noise/detection floor.

When verified internal-cache disable is unavailable, use disjoint deterministic
identity banks and counterbalance which build receives each bank. This reduces
order bias but remains a `driver_natural_unseen_key` experiment, not a strict
same-key driver-cold A/B result.

## Required manifest fields

Every native run must include:

```text
physical device name, vendor/device ID, driver ID/version
Vulkan API version and enabled extensions
pipelineCacheUUID
pipeline-binary internal-cache properties
requested/effective internal-cache disable state
application pipeline-cache mode and input byte count/hash
xemu history/SPIR-V namespace and manifest hashes
Mesa/vendor environment controls
process/device generation
exact xemu/XISO/build/symbol identities
validation/instrumentation/failpoint state
compile-required probe and creation-feedback support
compiled live capacities and prewarm allowance
```

Missing fields produce `cache_qualification_incomplete`. They must not be filled
with inferred defaults.

## Revised acceptance statement

The design direction remains useful, but the PR is not implementation-ready
until this audit is reflected in the native work. A completed suite may support
these claims independently:

1. **Correctness:** supported fallback and specialized routes produce approved
   observations for the selected states.
2. **Lifecycle:** exact demand, queueing, compilation, publication, and first
   specialized submission are joined without missing events.
3. **Compiler isolation:** only runs with verified internal-cache disable may be
   called driver-internal-cache-disabled.
4. **Practical performance:** normal-cache cold/warm campaigns show whether a
   candidate reduces user-visible stalls.
5. **Coverage:** the accepted fixed synthetic packs cover documented production
   state buckets and required capacity boundaries.

None of those claims can be inferred from the 96-entry design matrix, a
successful XISO build, or stable final-frame hashes alone.

## Primary references

- xemu pipeline-key canonicalization and uniform stripping:
  `hw/xbox/nv2a/pgraph/vk/pipeline-key.h`
- xemu live capacities and cache-key types:
  `hw/xbox/nv2a/pgraph/vk/renderer.h`
- xemu application pipeline-cache load/save/create paths:
  `hw/xbox/nv2a/pgraph/vk/draw.c`
- xemu family replay codec and validation:
  `hw/xbox/nv2a/pgraph/vk/hybrid-family-codec.c`
- xemu prewarm launch allowance:
  `hw/xbox/nv2a/pgraph/vk/hybrid-prewarm.h`
- Vulkan internal-cache control:
  <https://docs.vulkan.org/refpages/latest/refpages/source/VkDevicePipelineBinaryInternalCacheControlKHR.html>
- Vulkan internal-cache properties:
  <https://docs.vulkan.org/refpages/latest/refpages/source/VkPhysicalDevicePipelineBinaryPropertiesKHR.html>
- Vulkan compile-required control:
  <https://docs.vulkan.org/refpages/latest/refpages/source/VK_EXT_pipeline_creation_cache_control.html>
- Vulkan creation feedback:
  <https://docs.vulkan.org/refpages/latest/refpages/source/VkPipelineCreationFeedback.html>
- Mesa on-disk shader-cache control:
  <https://docs.mesa3d.org/envvars.html>
