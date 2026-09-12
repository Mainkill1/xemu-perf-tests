# PR71 shader-binding delay: step-by-step diagnosis

**Status:** Diagnostic source investigation, not a product fix or performance qualification. Product head: [`48059eae`](https://github.com/Mainkill1/xemu/commit/48059eaea0d6203013bf409ecb926b092a692ee8). The candidate remains draft. This report separates the repeated warm-path cost from occasional graphics-pipeline creation and other long frames.

## What the existing result means

The earlier 15-second PGR2 Vulkan snapshot capture recorded **4.540 ms of shader-binding CPU time per guest frame with Hybrid On**, accumulated across **4,771 calls per guest frame**—about **0.95 µs per call**. Hybrid Off on the same candidate recorded 4.414 ms. These are instrumented diagnostic measurements, not a normal-run FPS result. The 0.126 ms On/Off gap in that single pair is small relative to the shared 4.4 ms cost; a prior 30-second pair measured a 0.060 ms gap. [Prior capture and source identities](../diagnostic-r6/README.md).

The product call order ([texture binder](https://github.com/Mainkill1/xemu/blob/48059eaea0d6203013bf409ecb926b092a692ee8/hw/xbox/nv2a/pgraph/vk/texture.c#L1667), [shader binder](https://github.com/Mainkill1/xemu/blob/48059eaea0d6203013bf409ecb926b092a692ee8/hw/xbox/nv2a/pgraph/vk/shaders.c#L1434), [uniform decision](https://github.com/Mainkill1/xemu/blob/48059eaea0d6203013bf409ecb926b092a692ee8/hw/xbox/nv2a/pgraph/uniform-stage-update.h#L22)) is:

1. `create_pipeline()` binds textures, then calls `pgraph_vk_bind_shaders()`.
2. Shader binding checks completed background work and reads shader dirtiness.
3. A dirty hint rebuilds the effective shader state; the complete state is compared with the current binding.
4. An unchanged specialized binding skips route lookup. Otherwise the route selector probes cached bindings/modules and may prepare a fallback.
5. Binding replacement, if needed, updates module/layout ownership.
6. Uniform-stage needs are evaluated. Requested stages compute/copy values and update dirty bookkeeping.
7. Descriptor-set/UBO work follows outside `pgraph_vk_bind_shaders()`; its time is **not** included in the shader-binding figure.

## Step timing, controlled short capture

The schema-7 diagnostic source `74bc71d4` samples the first eight binds of each guest frame and every 16th bind afterward. Both 15-second Off/On cells completed 428 guest frames with ~306 sampled binds per frame. The original whole-function timer still observes every bind. Timed steps are exclusive; the existing route and cache timers are nested inside them and must not be added again. [Exact identities and values](phase-metrics.json).

| Shader-binding step | On µs per sampled call | Share of sampled wrapper | Execution frequency |
| --- | ---: | ---: | --- |
| Completion check | 0.036 | 3.0% | Every bind |
| Dirty-state check | 0.055 | 4.7% | Every bind |
| State derivation and equality | 0.204 | 17.3% | Every bind; state rebuilt on ~3,084 |
| Route decision | 0.099 | 8.4% | Every bind; cache route helper entered ~509 |
| Binding selection/replacement | 0.036 | 3.1% | Every bind; replacement on ~509 |
| Uniform-needs evaluation | 0.126 | 10.7% | Every bind |
| Uniform value/copy work | **0.594** | **50.4%** | Every bind in this window |
| Final bookkeeping/residual | 0.027 | 2.3% | Every bind |

The sampled wrapper averaged 1.178 µs per sampled call, versus 0.978 µs across all calls in this more heavily instrumented build. Sampling and added clock reads can change the cost, so the percentages identify where sampled time went; they are **not** a precise production-time decomposition. The seven steps plus residual equal the sampled wrapper by construction. The trace recorded ~2,139 extra clock reads per guest frame beyond the existing wrapper reads.

## Why uniform work is requested on every draw

The schema-8 diagnostic `87132384` counted the actual `PGRAPHUniformStageUpdateInputs` predicates. The Off and On branch counts were nearly identical:

| Request/trigger | Off calls per guest frame | On calls per guest frame |
| --- | ---: | ---: |
| Shader binding / fragment-uniform update | 4,771 | 4,771 |
| Vertex and fragment uniforms both requested | 1,275 | 1,275 |
| Fragment uniforms only | 3,495 | 3,496 |
| `texture_bindings_changed` | **4,771** | **4,771** |
| Fragment source epoch changed | 2,925 | 2,925 |
| Vertex rows dirty | 1,191 | 1,192 |
| Inline vertex values in UBO | 0 | 0 |

Triggers can co-occur. The persistent texture-change flag is sufficient by itself to request the fragment check on every draw; source-epoch and layout changes also require checks on many draws. In the more detailed sampled uniform trace, the fragment setter, four texture-scale reads, and uniform value comparisons/copies cost **0.116 ms per guest frame across ~306 samples**. Vertex value/row work ran on ~79 of those samples and cost ~0.066 ms combined. These are **nested** within the sampled 0.230 ms uniform-update step in schema 8, whose additional counters increase diagnostic overhead.

An update request is not proof of a GPU UBO write. `apply_uniform_updates()` compares values, and the renderer marks a stage dirty only when a value or layout changes. The descriptor-set update happens later.

## Why the texture-change flag stays set

The schema-9 counter pass found that the texture binder took its **slow path on every measured draw** in both modes. Its first cause was nearly identical Off and On:

| First slow-path cause, per guest frame | Off | On |
| --- | ---: | ---: |
| Dirty enabled texture stage | 3,489 | 3,489 |
| Dirty disabled texture stage | 1,264 | 1,264 |
| Bound-memory dirty hint | 17 | 17 |
| Dirty-page scan / missing binding | 0 | 0 |
| Fast-path texture binds | **0** | **0** |

The code checks dirty flags for **all** four stages, including disabled stages. Its slow loop skips disabled stages without clearing their dirty flags. The capture found at least one disabled dirty stage after **4,710 of 4,771** slow binds per frame. This is a source-confirmed mechanism for persistent slow-path entry, but enabled-stage changes also account for most *first* triggers in this workload. Do not attribute all 4,771 slow binds to disabled-stage persistence.

The slow path unconditionally sets `texture_bindings_changed = true`. On about **1,043 binds per frame**, all four selected binding pointers, scale bit patterns, image views, and samplers were unchanged before and after that path. This is an unchanged **binding identity**, not proof that image contents were unchanged; an in-place texture or surface update can still require separate work. Conversely, pointer/descriptor changes occurred roughly **3,880 times per frame counted per stage**, so many slow binds are real selection changes.

The texture flag was the **sole fragment-uniform update trigger** on about **1,688 binds per frame**: no fragment source-epoch, layout, polygon-offset, or force-full trigger was present on those calls. This is the bounded population to investigate for avoidable fragment uniform work. Actual value-copy changes, descriptor writes, and image-content generations still need a direct correctness check before changing behavior. [All counters and source identities](phase-metrics.json).

## Long frames are a separate question

The prior schema-6 15-second On capture contains both kinds of event. Its worst guest interval, frame 928 at **62.641 ms**, had **4.258 ms** in shader binding and **9.713 ms** in pipeline preparation, both below that run's averages. Shader binding cannot explain that frame's excess. Frame 802 at **53.401 ms** had **7.569 ms** in shader binding and eight specialized graphics-pipeline creations totaling **11.285 ms**; that is a distinct creation burst. The prior >80 ms cold spikes remain unassigned. Nested regions and GPU waits must not be summed as independent causes.

## Limits and next action

The measured warm window selected **zero fallback bindings**, even with Hybrid On. This diagnosis cannot establish first-seen fallback cost or end-to-end benefit. Four short, diagnostic-only Off/On pairs progressively isolated the phases; instrumentation overhead rose as counters were added, so absolute timings from different schemas must not be treated as paired optimization results. No full XISO, PGR2 fresh start, or Morrowind run was repeated for this report. The exact [diagnostic instrumentation patch](diagnostic-instrumentation.patch.gz) decompresses to a patch that applies cleanly to product `48059eae`. Compressed SHA-256: `cd28a90c1219125620e402c7200a6a0fabc42bd4189395a44ee130fe3c9f8d4e`; patch SHA-256: `2fd11fbc7073a7bbebf8e4f12964b8c9b15a9d298524146de2de132cccd19ed7`. It was not merged into the product.

The next focused experiment should separate **texture state requiring examination** from **effective binding/scale identity changing**. In particular, a dirty disabled stage should not force repeated full revalidation while it remains disabled, but re-enabling it must still prepare the latest state. The flag passed to fragment uniforms and descriptors should reflect the values those consumers actually require. Before accepting such a patch, test real texture writes, palette updates, shared dirty pages, surface-backed texture content, disabled-to-enabled transitions, and failed upload/retry. Then compare candidate versus previous main and fixed baseline with normal-run captures. Do not treat the present diagnostic as proof of an FPS gain or a fix for the separately observed cold pipeline-creation burst.
