# PR #85 PGR2 CPU attribution before the overlap-cache experiment

This is a **diagnostic sample**, not another performance acceptance run.
The untraced two-order PGR2 comparison in [the current report](REPORT.md)
holds #85 because its p95/p99 guest-frame intervals are worse in both
orders. We sampled CPU stacks to identify added work without assigning
every interval change to that work.

| Identity | Value |
| --- | --- |
| Main control source tree / executable SHA-256 | `2301f1cc976f93e5a943e065c4e12e034f33869f` / `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6` |
| #85 source / executable SHA-256 | `8d9245ddeb5f13d23a5e3f2aafdb5144c4bdad30` / `0c0e11d66e5a2b0b75fad38c8bb5acf88b5291b1115a47c6ba501f262fce313d` |
| Workload / renderer | Same PGR2 Vulkan snapshot, input, seed, scale 1, and 30-second warmup |
| Measurement | 30 seconds per executable; WPR `CpuScheduler` CPU sampling and `xperf` steady-state markers |
| Trace quality | Both completed; zero dropped events; trace recording stopped after each cell |

The measured windows were 49.678–79.776 seconds for #85 and
49.726–79.817 seconds for main, relative to each trace's start. We
filtered to the xemu process and mapped instruction pointers using each
executable's recorded image-load base and its own symbol table. Positive
values in the final column below mean **more sampled self-CPU on #85**.

| Sampled xemu self-CPU | Main total | #85 total | Main ms/guest frame | #85 ms/guest frame | Added ms/guest frame |
| --- | ---: | ---: | ---: | ---: | ---: |
| `sync_vertex_ram_buffer` | 80.7 ms | 189.4 ms | 0.092 | 0.215 | **+0.123** |
| `pgraph_vk_bind_vertex_attributes` | 182.9 ms | 244.0 ms | 0.209 | 0.277 | **+0.069** |
| `pgraph_vk_download_surfaces_in_range_if_dirty` | 30.0 ms | 24.7 ms | 0.034 | 0.028 | -0.006 |
| `download_surface_to_buffer` | 4.0 ms | 5.0 ms | 0.005 | 0.006 | +0.001 |
| All xemu leaf samples, across threads | 41,651 ms | 41,775 ms | 47.49 | 47.47 | -0.02 |

The #85 trace admitted 880 guest frames; main admitted 877. The hot
instruction pointers within #85's `sync_vertex_ram_buffer` map in the
optimized disassembly to the inlined traversal of the active surface list
for `pgraph_vk_surface_overlaps_range`. The highest few instructions in
that loop account for roughly 100 ms of the 30-second sample. This is
direct evidence that the new exact-overlap check adds CPU work on this
workload. The total xemu sampled self-CPU is nearly tied because unrelated
paths vary in the opposite direction.

Sampling is approximate and reports **self CPU**, not inclusive call time
or GPU wait. The traced frame-time direction differed from the untraced
ABBA direction, so this diagnostic cannot establish that the overlap scan
caused the full p95/p99 regression. It justifies one bounded experiment:
cache exact range-overlap answers until a surface enters or leaves the
active set, while continuing to check/download dirty overlapping surfaces
before CPU vertex decoding. Recheck untraced parent/candidate performance
and the full correctness oracles before accepting that experiment.

The large raw ETLs and WPA tables are retained off-repository. This
public record preserves the executable identities, workload, timing
window, trace quality, symbol-mapping method, aggregate counts, and the
limit on the conclusion.
