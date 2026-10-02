# Retained x87 status checks and fixed-work timings

These three Xbox-capable leaves exercise actual x87 instructions. They support
xemu issue #236; emulator before/after measurements belong to its xemu PR.

| Leaf | Work per sample | Independent checks |
| --- | --- | --- |
| `cpu_floating_point.x87_status_vectors` | 6,153 cases | 6,144 injected TOP/condition/masked exception-bit/control-word combinations; nine live stack/cache/helper sequences; exact status and upper EAX |
| `cpu_floating_point.x87_status_ax` | 16,777,168 `FNSTSW AX` dispatches per body | EAX `a5a50000`, checksum `f1100000` |
| `cpu_floating_point.x87_compare_status_ax` | 16,777,168 `FCOM ST1` + `FNSTSW AX` pairs per body | EAX `a5a57000`, checksum `f0fb0000` |

`x87-status-qualification.json` selects these three leaves plus the existing
x87 arithmetic and SSE scalar controls. It requests three warmups, ten measured
samples per leaf, multiplier four and per-iteration completion, preserving the
existing controls' pinned work contract. Each timing sample contains four
bodies, hence 67,108,672 status reads in the aggregate. The reported raw
sample divides aggregate time by four: its units are microseconds per body
(16,777,168 status reads), including that body's per-iteration GPU wait.
Warmups and the final framebuffer validation/overlay are outside the samples. The host timing frequency must remain
unchanged between emulator builds. Inspect repeatability before interpreting
small differences; run physical ABBA and BAAB.

The plain workload isolates status reads with an empty stack. The comparison
workload keeps two equal finite values in the x87 stack. Its unrolled comparisons
keep populated translator caches around status reads. Odd outer iterations avoid
a power-of-two checksum collapsing to zero. Every measured body contributes to
the failure accumulator; a late passing sample cannot hide an earlier failure.
The guest saves/restores the surrounding x87 environment and register contents.

Condition/TOP vectors use the architectural `FLDENV` instruction and literal
expected state; `FNSTSW` memory is a separate corroborating read. They include
all eight TOP values, all sixteen condition-bit combinations, four masked
exception-bit patterns, and all four rounding modes/three defined precision
controls. The additional sequences exercise push/pop/FXCH, stack rotation,
subsequent dirty writeback and an `FXAM` helper boundary.
Six of these live cases explicitly select single and double precision, use
distinct exact operands with order-sensitive subtraction, preserve a second
live slot, consume read-only operands, and cross a helper or explicit branch
before checking writeback. This prevents equal operands and commutative
arithmetic from concealing an incorrect `FXCH` mapping.

The same header is compiled by the native instruction checker:

```sh
python3 -m unittest discover -s tests -p test_x87_status_workload.py -v
```

This host check validates the fixture against real x87 instructions; it does not
qualify an emulator. Native Xbox runs and hard/soft-FPU emulator runs are needed
for that. These tests do not alter comparison exceptions, cover ES/B injection,
exercise every state save path or qualify precise fault handling. The reduced
emulator candidate changes only AX reads and preserves the existing FP
writeback checkpoint; memory forms remain conservative.

## Independent reference derivation

`utils/x87_status_reference.py` derives the three new reference records without
reading a captured xemu result. `FNINIT` gives the plain AX literal; two equal
finite stack values plus `FCOM` give the comparison AX literal. Repeating that
literal 16,777,168 times yields the 32-bit checksum by integer multiplication.
The vector result is zero failed cases and fixed case count 6,153. These values
are also checked against real host x87 instructions.

Each leaf clears the entire 640x480 A8R8G8B8 framebuffer to a known color. The
hash covers little-endian BGRA bytes per visible row, excluding pitch padding,
after GPU completion and before overlay/text. FNV-1a of those generated pixels
is the framebuffer oracle; it is independent of xemu's renderer and captured
hashes. The same derivation reproduces the already-pinned scalar color hash.

The producer appends only missing IDs to a new reference file, rejects duplicate
IDs or replacement of any existing x87 oracle, preserves all existing records,
and writes input/output hashes and explicit specification-derived provenance.
It produces no reference timings and makes no retail Xbox conformance claim.
Revision 2 distinguishes the longer work and added numeric metadata from the
prior three leaves. Previous failed measurements remain evidence.

```sh
python3 utils/x87_status_reference.py --base PINNED_REFERENCE.json \
  --output NEW_REFERENCE.json --manifest NEW_REFERENCE.provenance.json
```

No newly captured framebuffer reference is approved. Unrelated reference
mismatches remain failures; this producer cannot replace their expected hashes.
