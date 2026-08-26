# Pipeline texture-switch workload capsule

`PipelineTextureSwitch` adds two independently selectable phases to the
existing single XISO. Both use only fixed-seed generated data and render 512
fixed textured quads per invocation.

- `pipeline.texture-switch` alternates two 64x64 linear A8R8G8B8 texture
  backings every draw. The format and shader stay fixed while texture offset,
  repeat/clamp address mode, and box/tent sampler state alternate.
- `pipeline.shader-negative-control` holds texture A, address mode, and sampler
  state fixed while the final-combiner source alternates between texture and
  diffuse every draw. This is the negative control for attributing a pipeline
  or shader counter change to actual shader state rather than texture identity.

The result metadata reports one active texture stage, phase count, operations,
draws, texture switches, sampler/address changes, and shader-state writes.
Counts are exact fixed work and scale only with the shared measurement
multiplier.

## Known input and output

Seed `0x50545357` generates two same-format solid texture backings: red
`FFFF0000` and blue `FF0000FF`. The backing FNV-1a KATs are `BDF93DC5` and
`C40ABDC5`; the complete recipe input KAT is `A9CA7145`. Both backings are
hashed again after F1/F2 and must remain unchanged.

Every invocation repeatedly overwrites four fixed quads. After F1, the guest
emits a separate F2 correctness fence and reads all four tile centers. Exact
rendered-pixel KATs are:

| Phase | Final tile colors | Pixel KAT |
| --- | --- | --- |
| `pipeline.texture-switch` | red, blue, red, blue | `BB0EC8ED` |
| `pipeline.shader-negative-control` | red, green, red, green | `08C5E8A1` |

The multiplier-aware terminal state is checked before each phase draws and
asserts a fixed solid standard framebuffer:

| Phase | Result color | `framebuffer_fnv1a64` |
| --- | --- | --- |
| `pipeline.texture-switch` | `FF18405A` | `8ae05d31fb00c325` |
| `pipeline.shader-negative-control` | `FF4A2038` | `f110c8bd6338c325` |

All failures use the live guest FAIL event path. A sparse heartbeat is emitted
every 32 invocations so a supervisor can distinguish slow progress from a
timeout without per-draw event overhead. All literal graphics oracles are
`REGRESSION_ONLY` until the same XISO is corroborated on a retail Xbox.

## Duration and selection

`resources/pipeline-texture-switch-fast-smoke.json` proves only routing and
correctness. Quick and sustained manifests use `batch_complete`, initial
128/64 and 320/160 warmup/multiplier plans, and select both exact phase IDs.
They are starting plans, not duration evidence.

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
