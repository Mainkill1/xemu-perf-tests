# Deliberate jump-cache collision workloads

Four retained CPU leaves extend `CpuTranslationBlocks`:

| Stable ID suffix | Targets | Stride | Purpose | Expected execution checksum |
|---|---:|---:|---|---|
| `jump_cache_collision2` | 2 | 65 bytes | Minimal repeated eviction | `4F71ED44` |
| `jump_cache_collision8` | 8 | 65 bytes | Set intended to fit eight victim entries plus primary | `52F08FDA` |
| `jump_cache_collision10` | 10 | 65 bytes | Exceed that combined capacity | `9D8149E6` |
| `jump_cache_noncollision8` | 8 | 64 bytes | Equal work and checksum with distinct primary slots | `52F08FDA` |

Each iteration makes **8,000,000 round-robin indirect calls**, starting with
`0x12345678`. A target loads its cdecl argument, XORs `(target_index+1)*0x9E3779B9`,
rotates left by seven, adds `0x7F4A7C15`, and returns. Arithmetic wraps at 32 bits;
the caller supplies `state XOR operation_index`. The test profiles ten samples
using the existing multiplier/warmup/completion settings. Allocation/code generation, address checks, byte hashing, output and release
are excluded. Initializing the small volatile target-pointer table remains inside
each timed iteration (equal for the two eight-target cases); one checksum comparison per whole
work iteration records any failed sample. Code bytes are immutable during timing.

One 4 KiB `VirtualAlloc` page contains 18-byte routines. With the 4 KiB page and
4,096-entry softmmu hash in Mainkill1/xemu `76c23c7d`, offsets `i*65` for `i<10`
collide; `i*64` gives distinct slots. This describes xemu's software cache, not a
physical Xbox cache. The guest logs actual PCs and slots, asserts geometry and
checks that the generated page remains unchanged. Other emulator hashes require
fresh geometry analysis; these fixtures do not prove all lookups reach C dispatch
or that every hit is recoverable. Interrupts, loop/return PCs and capacity policy
can affect real recovery. Do not predict speedups from target count.

## Oracle and host qualification

The expected values above come from the independent Python integer recurrence
in `tests/test_jump_cache_collision_contract.py`. Host checks compile the actual
production emitter, execute its generated IA-32 code using an ELF32 Linux harness
without a 32-bit C library, and compare full budgets plus short known answers.
The ELF32 assembly harness has its own dispatch loop: it validates the emitter
and checksum recurrence, not production `Run()` or `Profile()`. Source and NXDK
object inspection cover the production call sequence and operation bound; native
guest execution remains required. Host tests independently extract hash bits for
four virtual-page bases, check invalid
counts, and verify all four catalog mappings. The host requires x86 Linux,
GNU `as`/`ld` and a C++17 compiler. It does not measure xemu performance.

```sh
python3 utils/test_catalog.py --check
python3 -m unittest discover -s tests -p 'test_*contract.py'
```

The generated catalog now has **163 leaves and five structural groups**. Shared
plans change only to bind the new catalog identity. Existing runtime workloads
and pinned historical ISO/catalog/reference identities remain separate. Do not
replace the old qualification image or its golden output with this build.

## Native acceptance still required

This source draft is suitable for later review/merge; it is not a qualified
paired benchmark yet. Build an immutable Release XISO and bind its embedded
catalog hash, executable/source/toolchain identities and prepared private HDD
through the maintained runner. Run each new leaf and an unaffected existing
control, retain every output, and verify the independent execution checksums.
The four new CPU leaves support an arithmetic-only runner reference from
`utils/cpu_jump_cache_reference.py`. It independently evaluates the 8M-operation
recurrence and specifies the entire immutable generated page, with byte and
execution hashes checked against actual emitted-code execution by the retained
host tests. It accepts no guest result input, records no framebuffer/timing
values, and refuses to overwrite a pinned file. This contract qualifies CPU work;
it does not qualify rendering. Native framebuffer output stays raw evidence and
is never promoted to a golden. Existing leaves still require their original
applicable references; the new tool does not waive those failures.

```sh
python3 utils/cpu_jump_cache_reference.py --output cpu-jump-cache-reference-v1.json
```

Before balanced testing, pin this reference's SHA-256 in a new suite/template
revision, keep historical suites unchanged, and verify each guest checksum.
The native pilot including DirectLoop remains a missing-reference failure;
a subsequent four-leaf arithmetic campaign is a new purpose and immutable
selection, not a replacement attempt or framebuffer approval.

Use fresh A/A and physical ABBA then BAAB on Deck `.123`; compare matched
uninstrumented parent, inline-only, recovery-bypass and real candidate as needed.
Keep useful-work times, absolute differences and positive-better percentages
separate from fixture qualification. Include capacity/noncollision regressions,
private Mesa cache evidence, and all failed attempts. Emulator evidence belongs
to the owning **xemu draft #301**, not evidence-only commits in this suite repo.
Real mapping, stale-entry/storage lifetime, reset/load and retail tests remain
separate gates; this synthetic workload does not satisfy them.
