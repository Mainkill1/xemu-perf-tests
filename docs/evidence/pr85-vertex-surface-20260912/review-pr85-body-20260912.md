# Vulkan: avoid false surface readbacks for adjacent vertex data

**Status: draft / correctness rework required before qualification.**  
**Issue:** [#84](https://github.com/Mainkill1/xemu/issues/84)  
**Base / current head:** `main` `9148241de690617ac0a21a26b41858585c1e3cab` → `2163208fdc49c7f6b4834bce98e6a11b494d4241`  
**Fixed cycle baseline:** `9f618d6d8c4c446ef023955f3d4de22f661f61a4`  
**Existing evidence:** [full report / compact results](https://github.com/Mainkill1/xemu-perf-tests/pull/33), [original page-overlap trace](https://github.com/Mainkill1/xemu-perf-tests/pull/32)

## Problem and intended repair boundary

The original Vulkan path widened vertex-memory synchronization requests to dirty-memory pages before checking whether GPU-authored surfaces overlapped them. In the pinned Morrowind snapshot this created false dependencies: page-expanded requests touched active surfaces even though the corresponding pre-alignment upload requests did not, causing unnecessary GPU→RAM downloads and synchronous `SURFACE_DOWN` waits.

The intended split is still correct:

| Decision | Required granularity |
| --- | --- |
| Does vertex consumption require GPU-authored surface data? | Guest vertex fetch span, before page expansion |
| Has guest memory changed? | Existing dirty tracking |
| Vulkan vertex-mirror copy | Page-aligned / ordered |
| Was the vertex mirror made stale by a GPU→RAM readback? | Vertex-mirror-owned freshness state |

The current patch moves the surface test before page alignment and largely removes the targeted `SURFACE_DOWN` path, but the current head still has correctness gaps in how the fetch span and freshness state are defined. Keep this PR narrow: fix vertex/surface coherency here; keep report retirement and later renderer-throughput work under #86/#87.

## Existing diagnostic result

These are **guest display writes / intervals, not presented FPS**. The short cells are diagnostic rather than merge qualification.

| Same-day Morrowind snapshot, Vulkan | Previous main | PR #85 | Change |
| --- | ---: | ---: | ---: |
| Guest display writes/s | 23.674 | 23.996 | +1.36% |
| Guest interval p95 | 50.076 ms | 48.498 ms | +3.15% |
| Guest interval p99 | 55.904 ms | 59.161 ms | -5.83% |

| Opt-in counter window | Previous main | PR #85 |
| --- | ---: | ---: |
| `SURFACE_DOWN` submissions | 193 / 242 guest writes | **1 / 244** |
| `NEED_BUFFER_SPACE` submissions | 243 / 242 | 245 / 244 |
| Median total sampled finish-fence wait | 12.423 ms/write | 11.808 ms/write |

This establishes that the targeted false-readback mechanism is real and is mostly removed. It does **not** establish an overall speedup. Later work shows other submission/report and vertex-copy/pass-break costs remain.

## Correctness blocker 1: define one canonical vertex fetch span

`pgraph_vk_bind_vertex_attributes()` currently queues:

```c
update_memory_buffer(d, start, num_elements * stride);
```

but computes `element_size = attr->size * attr->count` afterward. `num_elements * stride` is a pre-alignment upload request, not necessarily the enclosing bytes consumed by the attribute.

For a non-empty attribute range, use a checked enclosing fetch span:

```text
fetch_size = (num_elements - 1) * stride + element_size
```

Important cases:

| Layout | Current `count * stride` | Required enclosing span |
| --- | --- | --- |
| `stride > element_size` | Includes trailing padding | Smaller; avoid false trailing overlap |
| `stride < element_size` | Omits the final element tail | Larger; do not miss true overlap |
| `stride == 0` | Zero bytes | One `element_size`; CPU still reads the constant/current attribute |

This is an **enclosing span**, not a claim that every byte inside it is fetched; stride gaps may remain. That conservative representation is sufficient for the bounded repair.

Use checked arithmetic for both the start and extent. Validate the complete interval against the mapped DMA object before forming a pointer. Conceptually:

```c
element_size = attr->size * attr->count;
start_offset = attr->offset + min_element * stride;
fetch_size = (num_elements - 1) * stride + element_size;

/* checked multiply/add above */
if (start_offset > dma_len || fetch_size > dma_len - start_offset) {
    error_report("Invalid Vulkan vertex fetch range");
    abort();
}
```

Use the project's preferred checked-arithmetic helpers/conventions rather than copying the pseudocode literally.

Also update evidence terminology: existing traces using `count * stride` should be called **pre-alignment upload requests** unless `element_size`, stride and the corrected span are reconstructed. Do not silently relabel historical data as exact fetched bytes.

## Correctness blocker 2: resolve GPU-authored bytes before CPU attribute decoding

The current ordering is:

```text
pgraph_vk_bind_vertex_attributes()
  -> pgraph_update_inline_value() reads CPU-side VRAM
sync_vertex_ram_buffer()
  -> overlapping dirty surface may be downloaded
begin_draw()
  -> current/uniform values are consumed
```

A later readback cannot repair a value already decoded from stale CPU-side VRAM. `stride == 0` is the clearest case because the decoded value becomes a uniform/current attribute; nonzero-stride provoking/current values are also read before synchronization.

The corrected ordering should be:

```text
For each active VRAM-backed attribute:
  1. calculate element_size
  2. calculate checked start + canonical fetch span
  3. validate the full interval against the DMA mapping / VRAM
  4. resolve any dirty GPU-authored surface intersecting that span
  5. queue the same span for later vertex-mirror synchronization when needed
  6. only then dereference guest RAM for current/uniform attribute decoding

After attribute preparation:
  7. page-align and merge queued mirror ranges
  8. test ordinary guest-memory dirty state plus vertex-mirror-specific stale state
  9. record/direct the ordered copy
  10. record the draw
```

For `stride == 0`, the CPU value still requires surface coherency before decode, but no normal Vulkan vertex-buffer range needs to be bound for that attribute.

## Correctness blocker 3: vertex-mirror freshness needs ownership

A successful `download_surface()` currently marks `DIRTY_MEMORY_NV2A` so a later vertex draw can refresh the Vulkan vertex mirror. That is useful, but **do not make that shared dirty bit the sole proof of vertex-mirror freshness yet**.

`update_surface_part()` also calls `memory_region_test_and_clear_dirty(... DIRTY_MEMORY_NV2A)` on the non-TCG path. A surface operation can therefore consume that indication without itself updating the Vulkan vertex mirror. A possible sequence is:

```text
other consumer downloads GPU-authored surface
  -> RAM becomes newer than the vertex mirror
  -> DIRTY_MEMORY_NV2A set
surface processing consumes that dirty indication
  -> vertex mirror still old
later vertex use sees no new download and no shared dirty bit
  -> dirty-bit-only upload logic could skip the required refresh
```

The current `surface_overlap` force-copy behavior is conservative and should not simply be deleted until this ownership issue is resolved.

**Preferred long-term repair:** add vertex-mirror-specific page freshness/staleness state owned by the Vulkan vertex mirror (for example a page bitmap or generation state in `PGRAPHVkState`).

- Set the affected pages stale after every successful GPU→RAM surface readback.
- Clear them only when the corresponding vertex-mirror update has been directly performed or safely recorded in-order.
- Keep ordinary `DIRTY_MEMORY_NV2A` for normal guest-memory changes.
- Upload when `guest_memory_dirty || vertex_mirror_stale`.
- Once that invariant is proven, `surface_overlap` can stop acting as a proxy for freshness and clean live surfaces will not force copies merely because they intersect.

If this PR stays minimal instead, retain the conservative overlap-derived refresh and add the cross-consumer tests below. Do not equate “no download happened in this helper call” with “the vertex mirror is current.”

## Freshness-range requirement: mark what readback actually writes

PR #85 currently marks `surface->pitch * surface->height` dirty for the vertex mirror, while surface overlap/bookkeeping uses `surface->size = height * MAX(pitch, width * bytes_per_pixel)`.

Do **not** blindly replace one with the other. Define and validate the actual guest-memory write footprint of each readback layout:

- **Linear destination:** `memcpy_image()` writes rows using the guest pitch. `pitch * height` is normally conservative; the final written byte is determined by row pitch and `MIN(pitch, width * bpp)`.
- **Swizzled destination:** `swizzle_rect()` writes the swizzled guest destination contiguously from the surface base; the relevant payload is based on `width * height * bpp`, not the linear row pitch alone.

For every downloadable layout:

1. calculate the guest write extent with checked arithmetic;
2. prove it is inside both VRAM and the applicable DMA mapping;
3. mark every page modified by the readback as vertex-mirror stale / dirty;
4. add a regression that consumes data from the last affected page after the surface is no longer available to provide a live-overlap fallback.

Using `surface->size` as a conservative invalidation extent is acceptable only after its bounds are proven for that layout. The existing DMA assertion based on `pitch * height` is not, by itself, proof that a larger extent is valid.

## Suggested implementation split

### `hw/xbox/nv2a/pgraph/vk/vertex.c`

- Move `element_size` calculation before range registration and before any guest-memory dereference.
- Create a checked helper for canonical fetch start/extent.
- Resolve dirty surface overlap before `pgraph_update_inline_value()`.
- Queue the same canonical span for nonzero-stride mirror synchronization.
- Validate the complete DMA interval, not only `attr->offset < dma_len`.

### `hw/xbox/nv2a/pgraph/vk/draw.c`

- Keep page alignment, sorting, merging, dirty tests and ordered copies.
- Separate “guest memory changed” from “vertex mirror is stale.”
- Do not remove the current conservative overlap refresh until vertex-owned freshness tracking or an equivalent proven invariant replaces it.

### `hw/xbox/nv2a/pgraph/vk/renderer.h`

- If using the preferred design, add bounded per-page vertex-mirror stale/fresh state.
- If retaining `MemorySyncRequirement.surface_overlap` temporarily, document that it is a conservative freshness fallback rather than evidence that a download occurred.

### `hw/xbox/nv2a/pgraph/vk/surface.c`

- Keep successful readback invalidation of the vertex mirror.
- Define the actual guest write extent for linear and swizzled readbacks and validate its bounds.
- Mark the vertex-owned stale state over every written page.
- Make zero-length overlap checks explicitly false.
- Preserve current readback failure semantics: stale CPU RAM must never be consumed as though the download succeeded.

## Focused validation required before broader game qualification

| Test | Required result |
| --- | --- |
| `stride > element_size`, surface only in trailing padding | No surface readback |
| `stride < element_size`, surface in final element tail | Readback and correct vertex result |
| `stride == 0`, GPU-dirty bytes under attribute | Readback occurs **before** CPU decode; correct uniform/current value |
| Adjacent false overlap → later true overlap | First use skips false readback; later use receives fresh data |
| Other-consumer readback → later vertex use | Vertex mirror refreshes |
| Other-consumer readback → intervening shared dirty-bit consumer → vertex use | Vertex mirror still refreshes |
| Other-consumer readback → surface eviction → vertex use | Vertex mirror still refreshes without a live-surface fallback |
| Multiple overlapping / adjacent attributes | Correct merged upload; no duplicated required download |
| Multi-page / page-boundary attribute | Correct bytes and ordering |
| Swizzled readback, consume last written page after eviction | Every written page is invalidated and refreshed |
| Surface map/invalidate failpoint | Draw does not consume stale data; state remains conservatively dirty/pending |
| Command-buffer rollover around readback/upload | Earlier draws retain old bytes; later draws see new bytes |
| Vulkan validation | Zero new VUID/order/lifetime errors |

Prefer deterministic value/framebuffer oracles over a generic “nonblack” image for the focused freshness cases.

## Diagnostic counters worth adding

Keep them opt-in and aggregate outside the timed region:

```text
vertex_fetch_spans
vertex_fetch_span_bytes
vertex_page_uploads
vertex_page_upload_bytes
surface_intersections_from_vertex_fetch
surface_downloads_from_vertex_fetch
clean_surface_intersections
vertex_mirror_stale_pages_marked
vertex_mirror_stale_pages_refreshed
vertex_refresh_due_guest_dirty
vertex_refresh_due_surface_readback
surface_readback_failures_from_vertex_fetch
```

These should distinguish exact/canonical fetch-span behavior from page-expanded upload work. Do not label clean-overlap-forced copies “redundant” until vertex freshness is independently known.

## Scope and follow-on work

- Qualify #85 correctness on its own before treating stacked results as acceptance evidence.
- #85 does not need to solve the remaining Morrowind frame limit; it needs to remove the false dependency without weakening coherency.
- [#87](https://github.com/Mainkill1/xemu/pull/87) is stacked on this PR and explores avoiding vertex-copy render-pass breaks. Its fixed-view results are separate from #85 qualification and must be rebased/rechecked after any #85 coherency changes.
- #86 remains responsible for the report/completion and remaining main-command-buffer investigation.

## Merge gates

- [x] Exact current candidate build and source identity retained.
- [x] Original false page-overlap path diagnosed; targeted `SURFACE_DOWN` submissions largely removed.
- [ ] Canonical checked fetch-span calculation implemented.
- [ ] Surface coherency moved before all CPU-side attribute decoding.
- [ ] Vertex-mirror freshness survives another consumer, dirty-bit consumption and surface eviction.
- [ ] Linear/swizzled readback write footprints are bounded and fully invalidate the mirror.
- [ ] Focused true/false/later-overlap, stride-zero, failpoint and rollover oracles pass.
- [ ] Current full XISO on Vulkan/OpenGL and Vulkan validation complete.
- [ ] PGR2/Morrowind broader paired qualification shows no material tail or work amplification regression.
- [ ] Rebase/recheck stacked #87 after #85 correctness changes.

**Decision: keep draft.** The false page-alignment dependency is valid and worth fixing, but merge only after the corrected fetch-span, CPU-read ordering and durable vertex-mirror freshness contract are demonstrated.