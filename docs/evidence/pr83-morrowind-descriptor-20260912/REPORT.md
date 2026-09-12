# Morrowind snapshot: Vulkan frame-path investigation

This is diagnostic evidence for [xemu PR #83](https://github.com/Mainkill1/xemu/pull/83). Its one-line descriptor-capacity candidate eliminated the targeted finish but **did not improve the measured Morrowind frame path**. The PR remains draft and should not merge on this result.

| Identity | Value |
| --- | --- |
| Previous-main runtime source | `6bf9e98cdee50fd73e936ff2bd5b485ce14ac4dc` (runtime tree `2301f1cc976f93e5a943e065c4e12e034f33869f`) |
| Current main at branch creation | `9148241de690617ac0a21a26b41858585c1e3cab` (runtime-equivalent documentation change) |
| Fixed cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` |
| Candidate | `46779cb09520f7dcc8b3c8db7cf379fb5e62eeb4`, graphics descriptor sets 1,024 → 2,048 |
| Control executable SHA-256 | `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6` |
| Candidate executable SHA-256 | `94ab387727c93815b91b91a01fb0da27588a885e3d80b72c406400e8c0f9518f` |
| Candidate toolchain/profile | Pinned Windows GCC toolchain `09fdc183…`, O2, full LTO, x86-v3, DWARF and assertions; `.debug_info` and `.debug_line` verified |
| Runner SHA-256 | `9994bd2d823e8557d39aef582fef8d7f37965d54caa52eaa09514e5d256307ed` |
| Workload | Pinned Morrowind snapshot, confirmed running, Start/B exit from pause, fixed 10-second uninterrupted diagnostic window |

Matched WPR GeneralProfile.Verbose and 500 ms whole-GPU samples were captured on the Windows test host. The three cells completed with nonblack final images and no trace loss. Raw ETLs remain retained on the test host; their checksums are recorded below. The opt-in Vulkan counter run used the same source/executable and snapshot in a separate 10-second capture. Its 417 counter frames matched all 417 guest-flip log entries by ordinal; 242 were inside the measurement window. The exact analysis tool is [`utils/summarize_vk_frame_perf.py`](../../../utils/summarize_vk_frame_perf.py); its compact output is [`previous-vulkan-10s.json`](previous-vulkan-10s.json).

| 10-second diagnostic cell | NV2A display writes/s | Guest interval p99 | Whole-GPU utilization mean | Main vCPU thread CPU, full ETL | Renderer thread CPU, full ETL |
| --- | ---: | ---: | ---: | ---: | ---: |
| Previous main, Vulkan | 23.592 | 58.686 ms | 33.7% | 9.898 s | 2.127 s |
| Previous main, OpenGL | 32.485 | 45.294 ms | 37.1% | 9.783 s | 4.169 s |
| PR #81 candidate, OpenGL | 32.290 | 44.712 ms | 39.0% | — | — |

Display writes are a guest-cadence proxy, **not displayed FPS**. These short cells are for attribution. The [60-second PR #81 controls](https://github.com/Mainkill1/xemu-perf-tests/pull/31) are the relevant performance comparison; their adverse OpenGL tail signal remains unresolved. Whole-GPU utilization does not identify per-process work or prove that GPU scheduling is irrelevant.

| Current-main Vulkan opt-in counter, measured frames | Result |
| --- | ---: |
| Draw/descriptor-update calls per guest frame, median | 1,151 |
| `NEED_BUFFER_SPACE` submits | 243 over 242 frames; all frames affected |
| Fence wait at that finish, median / p95 per frame | 9.479 / 14.677 ms |
| Descriptor-update region, median per frame | 10.024 ms |
| Descriptor-update region less nested finish wait, median | 0.569 ms |
| Draw-flush region, median per frame | 16.404 ms |
| Vertex staging, median per frame | 3.05 MB against 8 MiB capacity |
| Vulkan queue submits, median per frame | 6 |

The exact candidate build passed source-tree, build-option, and DWARF checks. A first launch used the wrong executable basename; the existing runner could not identify or close that renamed process, so the cell timed out before QMP readiness. The exact orphaned process was stopped, its disposable private HDD was removed, and the **same binary** was restaged as `xemu.exe`. That failed infrastructure cell is excluded. The successful second candidate cell completed with a nonblack final image, unchanged seed, deleted private HDD, and no remaining xemu/tracing processes.

| Matched 10-second Vulkan counter window | Previous main | PR #83 candidate | Interpretation |
| --- | ---: | ---: | --- |
| Guest display writes/s | 24.20 | 22.77 | Short diagnostic direction worse; not an acceptance result |
| Guest interval p99, runner calculation | 55.450 ms | 60.804 ms | Worse in this diagnostic cell |
| `NEED_BUFFER_SPACE` submits | 243 / 242 frames | 0 / 228 frames | Descriptor capacity was the trigger |
| Median `NEED_BUFFER_SPACE` fence wait/frame | 9.479 ms | 0 | Targeted wait removed |
| Median `SURFACE_DOWN` fence wait/frame | 0.981 ms | 10.611 ms | Wait shifted to the later surface operation |
| Median total sampled finish-fence wait/frame | 12.423 ms | 12.478 ms | No meaningful wait reduction |
| Median descriptor-update region/frame | 10.024 ms | 0.516 ms | Time moved out of this nested region |
| Median draw-flush region/frame | 16.404 ms | 18.316 ms | Region grew; do not claim a net win |

The per-frame call count stayed at about 1,151, and the candidate used a median of six queue submits per frame, like previous main. The candidate removed 243 early submissions but the `SURFACE_DOWN` submission remained mandatory for GPU-authoritative data. It waited for a longer command buffer. This is direct evidence that simply enlarging the graphics descriptor pool moves the synchronization point rather than removing the required work in this scene. The 10-second guest-cadence movement is a warning, not a stable estimate of the candidate's performance effect; no full-suite or 60-second qualification was run after the mechanism failed.

## Why Morrowind reaches the surface wait

A separate previous-main trace enabled only guest flips and selected surface events. In one 10-second window, it recorded **412 GPU→RAM downloads**: 205 each for two 128×128 swizzled color surfaces, plus two one-off downloads. There were zero `surface_cpu_read`/`surface_cpu_write` events. A second selective trace reproduced **424 downloads** in 238 guest frames and showed 3,220 direct render-to-texture events, with zero surface-to-texture compatibility failures. The two repeatedly downloaded surfaces also appeared in the direct render-to-texture set. These traces are diagnostic and were not used for timing acceptance.

The existing zero-loss ETL resolves the readback call chain in 27 sampled stacks: `download_surface_to_buffer()` → `download_surface()` → `pgraph_vk_download_surfaces_in_range_if_dirty()` → `pgraph_vk_update_vertex_ram_buffer()` → `sync_vertex_ram_buffer()` → draw completion. This identifies **vertex-RAM synchronization** as the observed readback caller, not a CPU surface callback or failed surface-to-texture compatibility. The samples establish a real path but do not count all readback calls. The next unresolved question is whether the page-aligned vertex-sync ranges truly consume the two GPU-authored surfaces or merely overlap them through coarse range merging. Removing the readback before resolving that ownership question risks stale vertex data.

The descriptor-update region **contains** its fence wait and draw-flush contains descriptor update; these times must not be summed. `pgraph_vk_update_descriptor_sets()` finishes with `NEED_BUFFER_SPACE` when either its 1,024 graphics descriptor sets or the uniform staging buffer is exhausted. `pgraph_vk_finish()` then submits Vulkan commands and blocks on `vkWaitForFences()`. A descriptor-update call can return without consuming a set, so 1,151 calls alone did not prove the descriptor limit. The one-variable capacity experiment provides the stronger evidence: it removed every measured `NEED_BUFFER_SPACE` finish while leaving the staging guard unchanged. Other workloads may still exhaust uniform staging or other buffers.

The full ETL spans setup and teardown as well as the 10-second measurement, so its thread CPU totals are **not** 10-second-window CPU utilization. The traces nevertheless show substantial vCPU work in both renderers. Sampled hot functions include TB lookup/dispatch; the earlier September 9 graphics-TLB scan hypothesis does not explain the Vulkan-specific gap in these matched traces: `tlb_reset_dirty_range_all()` collected 216 samples in Vulkan versus 494 in OpenGL. Audio SRC is a smaller shared cost. These are sampled IP counts, not measured function self-times. The forced Vulkan surface readback and fence wait are the stronger renderer-specific lead; an optimized, correctly ordered readback path has not yet been tested.

| ETL cell | SHA-256 | Trace loss |
| --- | --- | --- |
| Previous Vulkan | `4c26b2dabd66b788a72a82134b00312831e4db1e032d4df0e033c10c059d56c3` | zero |
| Previous OpenGL | `22dee99072c68951ae3060b3f3d5d48d74d302035f516c221dab691bcf369999` | zero |
| PR #81 OpenGL | `5f0b48fb52e3fc27752b84cc6fbe39e4462420f8edd6d93552cb510b7274fbb7` | zero |

**Decision:** hold PR #83 as a documented negative/neutral capacity experiment. The next useful diagnostic is a bounded record of exact vertex-sync intervals and overlapping surface ranges, followed by an exact-range negative control. Any repair must preserve GPU-authored vertex bytes when they are genuinely consumed; it should eliminate only a proved false overlap or safely replace the readback with an ordered GPU copy. A new candidate then needs opposite-order uninstrumented Morrowind snapshot runs before full retail/XISO qualification. The fixed baseline remains unchanged.
