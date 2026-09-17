# PR #89: Morrowind gain and PGR2 tail, source and CPU-trace audit

**Status:** the Morrowind fixed-scene gain is real within its measured scope; the adverse PGR2 snapshot p99 is unresolved. Keep #85/#87/#89 draft. This audit identifies a precise bookkeeping defect in #89, but does not assign the PGR2 tail to it or qualify a merge.

## Exact source and trace identities

| Role | Current source / tested equivalent tree | Win64 executable SHA-256 |
| --- | --- | --- |
| #87 parent | `1d4524a6df0fac5822c7c8d0393a4ef5f6f16d6a` / tested `b3b99fb8832b658a653d53641170da3171ab2e6c` | `54b879eb2602c57504e97f2899ee73b91aa22debca4373465896a40b6d8a57e2` |
| #89 candidate | `cbb3b4372f756ad6bc6e6a725de36be84742b7bd` / tested `150d74ac5525be769e4f44ab35718eb2607a8eec` | `29eac8120cce296e312ba85147109ca5d6b62755d6326d36d4c0358a44231d25` |

The current heads and tested commits have matching source trees. The build audit verifies the pinned Release build and executable hashes. A wrong executable, skipped compilation, or accidental merge is not supported by the available identities.

The new 30-second PGR2 Vulkan CPU/scheduler trace pair used the same snapshot, B-3 input, 30-second warmup, and exact executables above. Both ETLs report zero lost buffers/events; recording and export processes were closed. The first CPU-table export accidentally selected only idle samples and was discarded. A second export from the **same ETLs** used the valid sampled-CPU table. No new emulator runs were made for the re-export. Raw ETLs and detailed stacks remain off-repository.

## What #89 actually saves in Morrowind

#87's `sync_vertex_ram_buffer()` calls `pgraph_vk_update_vertex_ram_buffer()` when a dirty page conflicts with a prior fixed-buffer read. That update records a staging-to-fixed-buffer transfer with vertex-input/transfer barriers and may end a render pass. If staging is exhausted, it finishes and waits before reusing the buffer.

#89 instead allows a small, bounded draw to pack its current vertex attributes into a private inline slice before recording. It leaves the fixed mirror stale until a safe repair. A prior draw can continue to read its old fixed bytes while the later draw reads the new inline bytes. This removes an ordered copy for **eligible dirty conflicts**, not for every selected draw.

A preliminary opt-in Morrowind diagnostic logged 767,705 versioned draws across 1,038 guest frames, about 740 selections/frame. These include repeated uses of already-stale pages; **767,705 is not a count of #87 uploads avoided**. The current reconciled heads nonetheless showed paired fixed-scene guest display-write cadence improvements of **+5.16% and +4.81%** in opposite run orders, with p95/p99 intervals improving in both pairs. This is a fixed-scene guest-progression result, not displayed FPS or a map-traversal result. Parent-side staging-copy and render-pass-ending counts were not captured in that Morrowind pair, so the exact saved-work budget is not established.

## A concrete #89 source mistake: private draws are counted as fixed-mirror reads

`sync_vertex_ram_buffer()` currently copies every merged source range into `pending_vertex_ram_reads`, even when it returns `versioned=true`. `begin_draw()` then sets `vertex_ram_read_pages` for those ranges. But when `versioned=true`, `remap_unaligned_attributes()` includes every active attribute and `bind_vertex_buffer()` binds each one to `BUFFER_VERTEX_INLINE`, not `BUFFER_VERTEX_RAM`. Those pages were **not** read from the fixed mirror by that draw.

This false read footprint can matter when one attribute page forces versioning and another active attribute page has no earlier fixed-mirror reader. The versioned draw marks both as read. A later guest write to the second page is then unnecessarily denied a safe direct mirror update and may select another inline version. The correct footprint is the fixed-buffer subset actually bound by the recorded draw; for an all-attribute version, it is empty. Preserve genuine earlier fixed reads when correcting the marker.

The same function sets `vertex_ram_updated_in_batch=true` before deciding to version and skip the mirror upload. Its name and finish-path use describe a mirror update that did not occur. This can keep read tracking active across batches. It may also intentionally preserve the optimization while stale pages exist; change that state only after separating those purposes and proving the resulting behavior. Neither finding is evidence of wrong pixels in the published oracle. The false-read case needs a focused multi-attribute same-page/different-page regression before changing it.

## What the PGR2 evidence says, and does not say

| PGR2 Vulkan snapshot comparison | #87 | #89 | Interpretation |
| --- | ---: | ---: | --- |
| Earlier uninstrumented 60-second pair 1 p99 | 42.386 ms | 44.536 ms | #89 **−5.07% Improvement** |
| Earlier uninstrumented 60-second pair 2 p99 | 42.388 ms | 43.513 ms | #89 **−2.65% Improvement** |
| New traced 30-second p99 | 44.022 ms | 44.120 ms | Near tie under tracing; not an acceptance run |
| New traced maximum | 49.964 ms | 50.086 ms | Both have similar worst events |
| Opt-in version selections in matched PGR2 diagnostic | 0 | 0 | Version-copy route absent in that measured scene |

The new trace's measured windows contained 885 #87 and 877 #89 guest frames. Symbolized xemu self-CPU across concurrent threads was approximately **47.91 versus 48.14 sampled ms per guest frame**; graphics/PFIFO thread sampled CPU was **8.31 versus 8.20 ms/frame** (#89 slightly lower), while guest CPU/TCG was **11.36 versus 11.77 ms/frame** (#89 higher). The modified `sync_vertex_ram_buffer()` sampled at **0.139 versus 0.148 ms/frame**; remap sampled at **0.120 versus 0.086 ms/frame**; surface-overlap/download traversal sampled at **0.192 versus 0.252 ms/frame**. The largest #89 traced interval was about 50.0 ms, with guest CPU active for roughly 49 sampled ms; #87 also had a roughly 50.0 ms interval with similarly high guest CPU activity. Sampling is not an exact synchronous time budget, and CPU work on concurrent threads must not be added as though it were wall time.

These observations rule out a **large directly measured version-copy cost in this PGR2 window**. They do not prove #89 has no indirect scheduling or code-layout effect, and tracing changes timing. The direct #89 no-version path adds only small source checks and a refactored remap/reservation sequence; the sampled graphics-thread work does not explain the earlier 1–2 ms p99 interval difference. Guest work and host scheduling remain possible contributors. The earlier adverse uninstrumented p99 results still block merge under the current acceptance rule.

## Where the investigation went wrong

The earlier response treated another broad benchmark as the next answer. That conflated three questions: whether the 5–6% Morrowind fixed-scene gain persists, what source work produces it, and why PGR2 snapshot tails moved. It also risked treating every version selection as a prevented parent upload. The source and trace now separate those questions. Repeated timing alone cannot identify a code defect.

The next code step is the narrow fixed-read-footprint correction, with a deterministic oracle where one active attribute page has an earlier fixed read and another does not. Measure whether the second page can repair directly while output generations remain correct. Separately, attribute any PGR2 tail to guest CPU work, ready-to-run delay, driver wait, or a specific no-version call path before editing that path. Do not change the 256-vertex/64-KiB policy or merge the stack based on this audit.
