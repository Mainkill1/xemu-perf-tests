# Vulkan submission-lifetime validation plan

This plan reuses eleven deterministic guest leaves to validate resource
pinning, cache eviction, vertex-read lifetime, report retirement, and renderer
teardown changes without inventing a synthetic host-only workload.

The selected leaves cover queued vertex writes, PGR2-sized draws, surface and
pipeline churn, texture binding reuse, fenced S3TC streaming, an explicit GPU
wait control, GPU-to-CPU surface reads, downloads, disjoint same-page vertex
RAM, and vertex-shader inline-buffer draws. Together they exercise the
graphics, texture, surface, vertex, fence, and retirement paths that can keep
Vulkan objects live across a submission boundary.

Use `resources/vulkan-submission-lifetimes-fast-smoke.json` for routing and
correctness only. Quick and sustained plans use fixed 1/4 and 2/16
warmup/multiplier starting points. Calibrate the control build before making a
timing claim, then run identical catalog and plan IDs on control and candidate.

## Required host evidence

Correlate counters separately for each leaf's F0/F1 interval. A candidate is
valid only when:

- Vulkan validation reports no destroyed, reset, or overwritten resource that
  is still referenced by an in-flight command buffer;
- submission pin/retirement underflow, conflict, and forced-eviction counters
  remain zero;
- every submitted slot reaches retirement in serial order, and final teardown
  leaves zero live pins and zero in-flight slots;
- vertex RAM synchronization covers the complete emitted fetch span; and
- the framebuffer/input/output oracle for every selected guest leaf passes.

Performance evidence is the per-leaf control/candidate distribution, not the
aggregate wall time of this mixed plan. Report medians and p95 values and flag
any leaf whose candidate p95 regresses by more than 5% across at least five
paired runs. The threshold is a triage gate, not a universal hardware claim.
