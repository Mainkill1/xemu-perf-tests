# Generated-code CPU fixtures

`cpu_translation_blocks.code_stable` and
`cpu_translation_blocks.code_rewrite` are paired fixed-work leaves for
[xemu research #245](https://github.com/Mainkill1/xemu/issues/245).
Their first revision uses 1,000,000 operations per sample and the suite's
existing ten measured samples, before any runner multiplier or warmups.

Each operation calls a generated `mov eax, imm32; ret` function in a separate
4096-byte executable allocation. Its entry is at byte 3, so the immediate at
byte 4 is naturally aligned. The stable leaf keeps `0xA5A55A5A` in that operand.
The rewrite leaf stores `0xA5A55A5A` on even iterations and `0x5A5AA5A5` on odd
iterations. Both execute CPUID leaf zero before each call. CPUID supplies the
serialization required for executing changed code; see the self-modifying code
section of the [Intel architecture manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html).

The checksum starts at `0x12345678`. For operation index `i`, rotate the checksum
left five bits, XOR the function's return value, then add `i * 0x9E3779B9`, all
modulo 2^32. The fixed-work known answers were computed independently from
this recurrence, without executing guest code:

| Operations | Stable | Rewrite |
| ---: | --- | --- |
| 0 | `12345678` | `12345678` |
| 1 | `e32f9558` | `e32f9558` |
| 2 | `5e8f6aff` | `dddf8872` |
| 3 | `b0b6f923` | `5ac34773` |
| 16 | `87414987` | `da7190d8` |
| 1,000,000 | `2fd8b528` | `65151d67` |

Allocation, initial code construction, deallocation, assertion, and rendering
are outside `Profile`. Its body includes the fixed-work loop, result stores,
and one checksum comparison per sample. An accumulated mismatch flag checks
every warmup and measured sample, including failures followed by a passing
sample. The suite's existing timing and GPU completion settings still apply.
`CPU_WORK` reports the operation count and final checksum.

The native Linux x86 contract test executes this same helper in executable
memory against all twelve literal known answers. Its negative control compiles
a temporary copy with code stores suppressed; the rewrite oracle must reject
the stale function at operation count two. Run it with the maintained host
contract command:

```sh
python3 -m unittest discover -s tests -p 'test_*contract.py'
python3 utils/test_catalog.py --check
```

The pair isolates repeated code writes while keeping call and CPUID work
comparable. The stable leaf is a proposed low-invalidation control: measured
emulator counters must establish that property. The rewrite leaf checks one
page and one aligned operand. It provides no coverage for remapping, spanning
pages, concurrent CPUs, cache reclamation, or reset/load transitions. A timing
difference between these leaves is not an optimization speedup. Both leaves
must pass through the runner on the measured emulator build before claiming
Xbox execution or using their timings as performance evidence.
