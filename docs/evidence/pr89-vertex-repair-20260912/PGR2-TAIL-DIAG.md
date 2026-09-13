# PGR2 snapshot tail: source and trace attribution

**Decision:** the adverse PGR2 snapshot p99 remains unresolved. Keep #85/#87/#89 draft; this diagnostic does not qualify a merge or establish a vertex-version slowdown. Current #87 `1d4524a6df` and #89 `cbb3b4372f` have the same source trees as tested `b3b99fb` and `150d74a`. The guarded idle-bitmap-clear experiment was [reverted](IDLE-CLEAR.md) after an adverse A/B result.

| Comparison | Exact tested binaries | PGR2 snapshot p99 Improvement % | Relevant observation |
| --- | --- | ---: | --- |
| #85 → #87, first / reverse order | `e9d763da` → `54b879eb` | **−2.79% / −2.00%** | Adverse in both orders |
| #87 → #89, first / reverse order | `54b879eb` → `29eac812` | **−5.07% / −2.65%** | Adverse in both orders |
| #87 → guarded-clear experiment, first / reverse order | `54b879eb` → `131a1732` | **−2.32% / −1.00%** | No recovery; reverted |

Positive Improvement % means a shorter guest-frame interval. All results used the same PGR2 Vulkan snapshot, B-3 input, 30-second warmup, and 60-second uninstrumented measurement per cell. [Full cells and exact IDs](RECONCILED.md) · [failed experiment](IDLE-CLEAR.md).

A separate matched **diagnostic** pair enabled opt-in Vulkan counters for #87 and #89. Both recorded **zero vertex-version selections/draws, zero vertex-staging copies, and zero version bytes** over roughly 1,766 guest frames. The PR #89 version-copy path therefore was not exercised in this scene. Diagnostic `draw_flush` CPU totals were 20.18 ms/frame on #87 and 19.71 ms/frame on #89; instrumented timings are excluded from acceptance.

A 30-second CPU/scheduler trace pair compared #85 and #87, with zero lost ETW events/buffers and all trace/export processes closed afterward. Sampled xemu self CPU was about 47.50 versus 47.63 ms **across concurrent xemu threads per guest frame**. The `sync_vertex_ram_buffer` self samples were 0.117 versus 0.149 ms/frame, an increase of about 0.032 ms/frame. This identifies some added work, but the aggregate sample difference is much smaller than the 1–2 ms p99 interval movement and does not assign its tail cause. The largest traced #87 frame was 78.829 ms; its sampled xemu work included roughly 15 ms in `cpu_exec_loop`, 29 ms in audio resampling, and no dominant vertex operation. This single frame does not establish that any of those functions caused its delay.

The uninstrumented #87/#89 frame logs overlap at 1,763 and 1,774 guest-frame IDs in the two pairs. Restricting each pair to identical frame-ID ranges leaves p99 Improvement at approximately **−5.09% and −3.35%**. The long intervals occur at different frame IDs across runs; per-frame interval correlations are only 0.016 and 0.116. This supports a variable event or scheduling component, but **does not prove** the patch is innocent. Across the four cells, median NVIDIA graphics clock changed from 615 MHz in the first two runs to 540 MHz in the last two regardless of binary; this host-state change also does not alone explain the within-pair difference.

The trace export is a sampling estimate, not an exact synchronous time budget. The raw ETLs and frame logs remain private on the test host; this public record retains the source/executable identities, bounded aggregate measurements, and negative findings without private paths. Next attribution should target a repeated bad interval and distinguish guest CPU execution, ready-to-run scheduling delay, Vulkan/driver wait, and game progression in the same frame. Avoid another broad code change based on the p99 sign alone.
