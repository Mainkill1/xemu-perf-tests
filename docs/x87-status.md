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
for that. The original three leaves do not alter comparison exceptions,
exercise every state save path or qualify precise fault handling. The reduced
emulator candidate changes only AX reads and preserves the existing FP
writeback checkpoint; memory forms remain conservative.

## Retained exception and fault checks

Two additional revision-one leaves keep correctness coverage separate from the
fixed timing workloads above. `x87-checkpoint-qualification.json` selects both;
`x87-exception-status-qualification.json` selects only the first. These use
three warmups, ten measured samples, multiplier four and per-iteration completion.
Their durations are diagnostic; passing them does not establish a speedup.

| Leaf | Cases per body | Check |
| --- | ---: | --- |
| `cpu_floating_point.x87_exception_status` | 384 | Each of six exception flags, masked or pending/unmasked; eight TOP values and four condition patterns; exact ES/B, status and upper EAX in nonwaiting AX/memory reads |
| `cpu_floating_point.x87_fault_checkpoint` | 4 | Dirty scalar or two live values, single/double precision, `FNSTSW AX`, then an actual inaccessible-page read; exact fault PC, saved FP control/status/tag/values, upper EAX and actual post-resume FP state |

The exception-status case loads consistent architectural environments, reads
status without `FWAIT`, then clears pending exceptions before any later waiting
instruction or return. It preserves the caller's complete saved x87 state.

The fault test allocates and releases its own inaccessible 4KiB page. The Xbox
adapter uses the existing nxdk structured exception mechanism and only accepts
a read access violation at the exact labeled load and owned page. It checks the
kernel's captured FP state and advances the exception PC to the next instruction.
Missing FP context is a failure, not a skipped check. Unexpected exceptions are
not intercepted. One sequence doubles exact 3 to 6; the other produces ST0=6,
ST1=3. No call or branch intervenes between dirty arithmetic, AX read and load.
After resumption, EAX is checked again. All cases restore the surrounding x87
state; allocation/release and capture-count failures remain failures.

The native Linux adapter runs the same instruction regions against a protected
page and inspects the signal's FP context. It corroborates the fixture's
instruction/format expectations; it does not validate the Xbox adapter or xemu.
Its negative controls omit dirty arithmetic, omit a stack update and destroy
upper EAX, and reset the actual resumed FP state. Both adapters check an
inline nonwaiting `FXSAVE` immediately after resumption, before `FNCLEX` cleanup,
against the same literal control, status, tag and value expectations; captured state alone cannot pass the test.
A further negative control corrupts only the OS continuation status after its
initial capture has passed. Exception-status negative controls remove ES/B, TOP
and upper EAX.
These checks catch their intended corrupted states. They do not substitute for
an emulator build deliberately missing its writeback checkpoint.

```sh
python3 -m unittest discover -s tests -p test_x87_exception_status.py -v
python3 -m unittest discover -s tests -p test_x87_fault_workload.py -v
```

Focused Deck validation of these two leaves is recorded in the owning xemu PR;
broader state-save and physical Xbox validation remain pending. The active game and timing campaigns keep their original
immutable ISO and reference; rebuilding these extra checks does not change those
campaigns or make their prior results apply to a new fixture.

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

The optional `--family exception-status` and `--family fault` append only the
selected new record, preserving all earlier records. Their expected case counts
are 384 and 4, failure checksum zero, with fixed solid framebuffer colors
`ff403020` and `ff203040`. They are derived from the literal test specification,
not captured emulator output. Use distinct, previously nonexistent output files:

```sh
python3 utils/x87_status_reference.py --base PRIOR_REFERENCE.json \
  --family exception-status --output EXCEPTION_REFERENCE.json \
  --manifest EXCEPTION_REFERENCE.provenance.json
python3 utils/x87_status_reference.py --base EXCEPTION_REFERENCE.json \
  --family fault --output CHECKPOINT_REFERENCE.json \
  --manifest CHECKPOINT_REFERENCE.provenance.json
```
