# Retained x87 status checks and fixed-work timings

These three Xbox-capable leaves exercise actual x87 instructions. They support
xemu issue #236; emulator before/after measurements belong to its xemu PR.

| Leaf | Work per sample | Independent checks |
| --- | --- | --- |
| `cpu_floating_point.x87_status_vectors` | 6,153 cases | 6,144 injected TOP/condition/masked exception-bit/control-word combinations; nine live stack/cache/helper sequences; exact status and upper EAX |
| `cpu_floating_point.x87_status_ax` | 1,048,336 `FNSTSW AX` dispatches | EAX `a5a50000`, checksum `b5500000` |
| `cpu_floating_point.x87_compare_status_ax` | 1,048,336 `FCOM ST1` + `FNSTSW AX` pairs | EAX `a5a57000`, checksum `b4e70000` |

`x87-status-qualification.json` selects these three leaves plus the existing
x87 arithmetic and SSE scalar controls. It requests two warmups, ten measured
samples per leaf, multiplier one and batch completion. Warmups and the final GPU
completion are outside each work sample. The host timing frequency must remain
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

No newly captured framebuffer reference is approved by this change. Existing
references stay unchanged. Missing references must remain visible and block full
performance qualification; numeric checks cannot silently replace that gate.
