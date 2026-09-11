# PR74: report bounds and idle retirement

**Status: planned validation, no native result yet.** [Product PR74](https://github.com/Mainkill1/xemu/pull/74) repairs [issue60](https://github.com/Mainkill1/xemu/issues/60). This evidence branch covers PR74 only.

The shared writer must validate the complete three-word descriptor read and all 16 destination bytes. The Vulkan queue must retire at FIFO idle even without an active command buffer. Existing GPU completion, captured DMA ownership, cumulative counts and the three little-endian stores are preserved.

## Predeclared focused checks

| Check | Required result | Coverage limit |
| --- | --- | --- |
| Final production serializer unit | Exact fits accepted; short spans perform no stores; bytes and neighbors correct | Helper and descriptor predicate, not full renderer wrapper |
| Zero query, both renderers | Valid zero report publishes | Fixture still draws; not a no-command-buffer proof |
| Single / multiple / clear boundaries | Published values and cumulative/clear behavior match oracle | Six selected controls do not qualify the full catalog |
| DMA target switch | Reports publish to their requested separate buffers | No descriptor-mutation redesign |
| DMA range guard | Invalid A1 leaves A canaries intact; subsequent valid B0 publishes | B is separate; zero B0 after clear is valid, not corruption |

Run the six controls once on each renderer with the exact candidate executable, plus the final unit under Wine and native Windows. Retain per-cell results and identities. Invalid-span execution is restricted to the fixed candidate; historical failures remain the reference. Existing retained baseline binaries are not rebuilt.

## Measurement limits

These are correctness checks. Diagnostic transport without live guest markers cannot qualify performance. A timeout becoming successful is not an FPS improvement. A dedicated no-draw/no-active-command-buffer observation remains required; the existing zero-query control does not supply it.

Full XISO, query-capacity/vertex ownership, PGR2 fresh-start and snapshot, Morrowind snapshot, and matched normal-path resource/frame-tail comparisons remain acceptance gates. Candidate versus previous main and versus the fixed baseline must be reported separately, with positive Improvement% favorable. No merge or baseline change follows from this focused dataset alone.

## Identity and evidence

[Planned manifest](planned-manifest.json) pins source, test image, catalog and runner. Final executable, build, hardware and result identities will be added after execution. No new test image is claimed: the staged current 157-record suite is reused.
