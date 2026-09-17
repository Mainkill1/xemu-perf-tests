# APU snapshot-load repair against main

**Merged as [xemu #53](https://github.com/Mainkill1/xemu/pull/53); the isolated repair passed the Morrowind snapshot cell on both renderers.**
The retained main-equivalent baseline reproduced the OpenGL DSP assertion;
the candidate changes only `mcpx_apu_pre_load()` in `hw/xbox/mcpx/apu/apu.c`.
No baseline was rebuilt and no baseline performance campaign was repeated.

Base: `586de4f32c11001c0abe072c3530236f1571b372`.
Candidate: `c17591d59c270b352b72e648f5ed65e4b2a3e77e`.
Tree: `6824a5aa4d9ca288ac96092dc9244684e995b08d`.
Executable SHA-256:
`3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b`.

The change extracts existing repair `ae9b0877a856cae0e4893c1f3413e1a9cb0357d8`
from later history. It releases the BQL before waiting for the APU frame thread
to become idle, then keeps that thread paused through VMState restoration.
The normal running-state callback synchronizes the restored DSP state and
resumes execution. Reset/state-change paths already establish this lock order.
Holding the BQL while waiting could deadlock the APU's IRQ publication path.

| Cell | Readiness and 20-second scene | Cleanup | Cadence / p95 / p99 |
| --- | --- | --- | --- |
| Existing baseline, OpenGL | DSP program-word assertion before readiness | Recovered and verified | Not measured |
| Candidate, Vulkan | PASS | Private HDD deleted; seed unchanged | 23.723/s / 47.990 ms / 57.134 ms |
| Candidate, OpenGL | PASS | Private HDD deleted; seed unchanged | 32.798/s / 38.098 ms / 42.848 ms |

The rates are guest display-write cadence, **not rendered FPS**. Candidate
timings are retained for future matching comparisons; there is no matched,
uninstrumented retail baseline timing result in this package and no performance
gain is claimed. Do not compare them with the slower temporary counter probe.

The existing input recipe, snapshot seed and runner/controller hashes were
unchanged. Builds used the baseline's O2/LTO options with symbols, assertions
and QOM cast checks. This candidate contains no causal counters. An initial
bundle import failed because the cached builder lacked the main commit; adding
that source prerequisite allowed the incremental build to pass. That bootstrap
failure occurred before compilation or native execution.

Both final images were manually inspected: expected outdoor bridge/building
scene, visible HUD crosshair, no pause/reconnect overlay. Automated nonblack
checks passed. This does not establish independent pixel accuracy or audio
quality. Full-suite/PGR2, repeated snapshots, DSP backend combinations and
injected load failures were not executed as part of these two focused cells.

[Manifest and final cleanup](manifest.json) · [Vulkan result](vulkan-run.json) ·
[OpenGL result](opengl-run.json) ·
[Baseline failure and reproduction recipe](../main-cause-20260909/REPORT.md#opengl-failure-and-existing-repair).
No game assets, snapshot disk, BIOS files or private system configuration are
included. The repair already has aggregate coverage in xemu #38/#51/#52; this
is new isolated-main qualification, not a claim of previously unknown code.

## Verified integration and baseline reuse

Main `bd1fecb93353272dda2a810991e28945de35b665` has exactly the tested candidate tree `6824a5aa4d9ca288ac96092dc9244684e995b08d`. The complete exact-source push CI build matrix [passed](https://github.com/Mainkill1/xemu/actions/runs/34340240452). Independent source review and the two native cells above informed the merge. The existing executable and these GL/VK measurements become the new main baseline without rebuilding. Previous main XISO summaries remain historical under their original identities. Neither the broader S release proposal nor new-main full-suite/PGR2 qualification is implied.
