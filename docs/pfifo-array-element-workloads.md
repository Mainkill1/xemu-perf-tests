# PFIFO array-element workload capsules

`PFIFOArrayElements` adds three generated, asset-free capsules to the existing
single XISO:

- `PFIFOArrayElements::pfifo.array-element16`: one 38-word
  non-incrementing `NV097_ARRAY_ELEMENT16` packet shape, repeated 256 times per
  fixed invocation. Each packet contains 76 indices and 19 complete quads.
- `PFIFOArrayElements::pfifo.array-element32`: the same 76-index geometry as
  the first capsule, carried by one 76-word non-incrementing
  `NV097_ARRAY_ELEMENT32` packet. This keeps rendered work equivalent while
  separating the 32-bit method handler.
- `PFIFOArrayElements::pfifo.array-element-pgr2`: one 29-word
  non-incrementing `NV097_ARRAY_ELEMENT16` packet shape, repeated 256 times per
  invocation. Its 58 indices contain 14 complete quads plus two trailing
  indices, preserving the observed packet length.

These shapes reduce trace evidence from Morrowind (38 words) and PGR2 (29
words). They do not contain title data and do not claim that every title packet
has these lengths.

Automation selects the catalog IDs
`pfifo_array_elements.array_element16`,
`pfifo_array_elements.array_element32`, and
`pfifo_array_elements.array_element_pgr2`. The historical names above remain
the guest execution IDs. All three supplied resource plans are catalog-bound
resolved plans; they intentionally cannot run against an XISO with a different
catalog ID.

## Known input and output

Seed `0x50464946` generates one shared 76-vertex tile grid. The literal logical
vertex KAT is `576F9C60`. The 76- and 58-index stream KATs are `214ABD05` and
`33E7DBF4`. Packet-payload KATs are `38503435` (38-word 16-bit), `214ABD05`
(76-word 32-bit), and `555DCC3C` (29-word 16-bit).

After F1, the guest waits for GPU completion, emits F2, and reads every complete
tile center. The 19-tile output KAT is `8F69B3C6`; the 14-tile output KAT is
`18D08B94`. It also asserts a multiplier-aware terminal guest state. Only after
those checks pass does it draw a fixed solid result frame and assert the exact
standard framebuffer FNV-1a hash:

| Test | Result color | `framebuffer_fnv1a64` |
| --- | --- | --- |
| `pfifo.array-element16` | `FF163826` | `9c884de2a5d32325` |
| `pfifo.array-element32` | `FF32764C` | `e079f0cf1a994325` |
| `pfifo.array-element-pgr2` | `FF291D52` | `bbc8b0702ffd0325` |

F0/F1 surrounds the fixed packet submissions, guest terminal-state fold, and,
for quick/sustained runs, one fixed batch-completion drain. That measured drain
prevents a baseline/candidate comparison from moving PFIFO/GPU tail work past
F1. Input preflight, output readback, hashes, result rendering, metadata, and
PASS/FAIL transport are outside the measured window. A separate post-F1 F2
correctness fence is mandatory even though batch-complete emitted an in-window
F2. The result metadata records packet and payload totals so a host telemetry
gate can compare them with decoded-method counters.

All literal graphics outputs are `REGRESSION_ONLY`. They become hardware
conformance oracles only after the same XISO is captured and corroborated on a
retail Xbox; a prior xemu result is not physical-NV2A proof.

## Duration and routing

`resources/pfifo-array-elements-fast-smoke.json` runs one warmup and multiplier
one for path/correctness validation. `resources/pfifo-array-elements-quick.json`
is the initial roughly 2-second warmup / 8-second measurement recipe.
`resources/pfifo-array-elements-sustained.json` is the corresponding initial
5-second / 20-second recipe. These duration labels are not evidence until a
baseline calibration measures them on the selected host. Quick and sustained
use `batch_complete`; smoke stays `enqueue` because it makes no performance
claim.

For a measured baseline per-invocation cost `u = total_us / iterations`, freeze
one shared baseline/candidate plan for each exact test ID:

```text
quick_warmup = ceil(2,000,000 / u)
quick_multiplier = ceil(8,000,000 / (8 * u))
formal_warmup = ceil(5,000,000 / u)
formal_multiplier = ceil(20,000,000 / (8 * u))
```

The three methods have different costs, so formal evidence should select one
exact ID and calibrate it independently from the baseline. Never calibrate the candidate
or compare different multipliers. Short smoke output can prove the
path and oracle only; it cannot support a performance claim.
