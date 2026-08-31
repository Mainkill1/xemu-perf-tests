# Pipeline texture-switch workload capsule

`PipelineTextureSwitch` adds four independently selectable phases to the
existing single XISO. All use only fixed-seed generated data.

- `pipeline.texture-switch` alternates two 64x64 linear A8R8G8B8 texture
  backings every draw. The format and shader stay fixed while texture offset,
  repeat/clamp address mode, and box/tent sampler state alternate.
- `pipeline.shader-negative-control` holds texture A, address mode, and sampler
  state fixed while the final-combiner source alternates between texture and
  diffuse every draw. This is the negative control for attributing a pipeline
  or shader counter change to actual shader state rather than texture identity.
- `pipeline.clear-texture-normal` executes 128 exact clear boundaries per
  invocation. Each boundary uses a clear pipeline, changes only texture offset,
  draws through the normal inline/immediate textured-quad path, changes only
  texture offset again, and issues a second normal draw. This generates 128
  clear-pipeline uses, 256 descriptor changes, 256 normal draws, and 640 total
  operations per invocation. The immediate path has zero Vulkan vertex
  bindings.
- `pipeline.sampler-only-identity` keeps one 64x64, five-level swizzled
  A8R8G8B8 image and all 5,456 backing words fixed. It alternates only LOD
  clamps (levels 0 and 2), box/tent filtering, repeat/border wrap, and border
  color. In-bounds UVs make the final tiles red, green, red, green.

The stable catalog IDs are `pipeline_texture_switch.texture_switch`,
`pipeline_texture_switch.shader_negative_control`,
`pipeline_texture_switch.clear_texture_normal`, and
`pipeline_texture_switch.sampler_only_identity`.

The result metadata reports one active texture stage, phase count, operations,
draws, texture switches, sampler/address changes, and shader-state writes.
Counts are exact fixed work and scale only with the shared measurement
multiplier. The clear-boundary phase reports its clear uses, descriptor
changes, normal draws, clear-to-normal transitions, safe texture-only
transitions, and zero-binding contract separately.

## Known input and output

Seed `0x50545357` generates two same-format solid texture backings: red
`FFFF0000` and blue `FF0000FF`. The backing FNV-1a KATs are `BDF93DC5` and
`C40ABDC5`; the original recipe input KAT is `A9CA7145`. The clear-boundary
recipe adds fixed clear color `FF202830` and has input KAT `1A404C43`. Both
backings are hashed again after F1/F2 and must remain unchanged.
The sampler-only mip backing KAT is `CDD5D7A5` and its recipe input KAT is
`2BC5C8EE`; all 5,456 words are rehashed after F1/F2.

Every invocation repeatedly overwrites four fixed quads. After F1, the guest
emits a separate F2 correctness fence and reads all four tile centers. Exact
rendered-pixel KATs are:

| Phase | Final tile colors | Pixel KAT |
| --- | --- | --- |
| `pipeline.texture-switch` | red, blue, red, blue | `BB0EC8ED` |
| `pipeline.shader-negative-control` | red, green, red, green | `08C5E8A1` |
| `pipeline.clear-texture-normal` | red, red, red, red | `50C0069D` |
| `pipeline.sampler-only-identity` | red, green, red, green | `08C5E8A1` |

The multiplier-aware terminal state is checked before each phase draws and
asserts a fixed solid standard framebuffer:

| Phase | Result color | `framebuffer_fnv1a64` |
| --- | --- | --- |
| `pipeline.texture-switch` | `FF18405A` | `8ae05d31fb00c325` |
| `pipeline.shader-negative-control` | `FF4A2038` | `f110c8bd6338c325` |
| `pipeline.clear-texture-normal` | `FF305060` | `22ba4f1405cda325` |
| `pipeline.sampler-only-identity` | `FF405020` | `0b8438c8404da325` |

For the dedicated clear-boundary manifests, the multiplier-aware terminal
states are `418E6684` (smoke multiplier 1), `BF18BC54` (quick multiplier 32),
and `96C62554` (sustained multiplier 80). Warmup work is excluded.

All failures use the live guest FAIL event path. A sparse heartbeat is emitted
every 32 invocations so a supervisor can distinguish slow progress from a
timeout without per-draw event overhead. All literal graphics oracles are
`REGRESSION_ONLY` until the same XISO is corroborated on a retail Xbox.

## Clear-pipeline runtime gate

The third phase is a host-counter gate for the Vulkan pipeline-binding fix.
For a measured candidate run:

- `PIPELINE_DIRTY_CLEAR_BINDING` must be greater than zero.
- The clear-to-normal boundary must be attributed as other dirty state, never
  as `PIPELINE_TEXTURE_ONLY_BYPASS`.
- After the normal pipeline is active, the second descriptor-only transition
  must make `PIPELINE_TEXTURE_ONLY_BYPASS` greater than zero.

The guest emits the ordered operation counts and exact output hashes. The host
must correlate counters only inside that test's F0/F1 interval. For an exact
measured interval, `PIPELINE_DIRTY_CLEAR_BINDING`,
`PIPELINE_TEXTURE_WITH_OTHER_DIRTY`, and `PIPELINE_TEXTURE_ONLY_BYPASS` each
equal the emitted boundary count. This exact bypass count proves the
clear-to-normal boundary was not misattributed. A counter miss is a path
failure even if framebuffer correctness passes.

## Sampler/image identity runtime gate

For `pipeline.sampler-only-identity`, the cold interval from `TEST_BEGIN`
through F0 must produce exactly one image cache miss/upload and exactly two
sampler cache misses. After warmup, the F0/F1 interval must produce zero image
or sampler misses while recording one sampler lookup per emitted operation.
Image identity changes are zero throughout. A different count is a path
failure even when framebuffer correctness passes.

## Duration and selection

`resources/pipeline-texture-switch-fast-smoke.json` proves only routing and
correctness. Quick and sustained manifests use `batch_complete`, initial
128/64 and 320/160 warmup/multiplier plans, and select the texture-switch,
shader-control, and sampler-only stable IDs.
They are starting plans, not duration evidence.

The dedicated `resources/pipeline-clear-texture-normal-*.json` manifests select
only the clear-boundary gate. Its initial quick plan is 64/32 and its sustained
plan is 160/80 because one invocation includes both clears and draws. These are
also control-calibration starting points, not portable timing claims.
The dedicated `resources/pipeline-sampler-only-identity-*.json` manifests
isolate the sampler/image cache split with the same 1/1, 64/32, and 160/80
smoke/quick/sustained starting profiles.

Calibrate each phase on the control build, then freeze the same fixed work for
control and candidate:

```text
quick_warmup = ceil(2,000,000 / control_invocation_us)
quick_multiplier = ceil(8,000,000 / (8 * control_invocation_us))
formal_warmup = ceil(5,000,000 / control_invocation_us)
formal_multiplier = ceil(20,000,000 / (8 * control_invocation_us))
```

Quick evidence must measure about 2 seconds of warmup plus 8 seconds inside
F0/F1. Formal claims require at least 5 seconds plus 20 seconds. Never calibrate the candidate.
Do not compare different work counts or treat a short smoke as performance evidence.
