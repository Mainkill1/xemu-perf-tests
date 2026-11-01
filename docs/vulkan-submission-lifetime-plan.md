# Vulkan submission-lifetime validation plan

This plan reuses eleven deterministic guest leaves to validate resource
pinning, cache eviction, vertex-read lifetime, report retirement, and renderer
teardown changes without inventing a synthetic host-only workload.

The selected leaves cover queued vertex writes, PGR2-sized draws, surface and
pipeline churn, texture binding reuse, fenced S3TC streaming, an explicit GPU
wait control, GPU-to-CPU surface reads, downloads, disjoint same-page vertex
RAM, three queued generations of one vertex allocation, and vertex-shader
inline-buffer draws. Together they exercise the
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
## Completed and pending CPU-read capsules

`surface.cpu_read_completed_surface` and `surface.cpu_read_pending_surface`
use three nonoverlapping 32×32 linear A8R8G8B8 surfaces in the existing
stage backing allocations. They save and restore those bytes outside profiling.
The resolved plan is `resources/surface-completion-readback.json`.

Both cases clear B, then A, drain guest commands, and read B. On Vulkan,
that read completes the batch while A, its final write, remains GPU-dirty.
They then clear C and drain guest commands. The completed case reads A
without another write. The pending control first clears A with a new color.
Both finish by reading C. These CPU reads validate every word against the
iteration's literal ARGB values, including warmups; colors change each iteration
so preceding contents cannot satisfy the next observation. A mismatch records
an oracle failure and remains visible to the runner.

`resources/surface-completion-reference.json` is independently derived from
the clear recipe, not from observed emulator output. It applies only to two
warmups, 20 measured bodies, multiplier 1, and `enqueue`: each case checks
67,584 words. The FNV32 observations are `7d41fdc5` (completed) and
`6105fdc5` (pending), in CPU observation order B, A, C. No captured framebuffer
is approved by these references. The same XBE can run on physical Xbox;
such execution has not yet been recorded.

Profile times include clears, command drains, downloads, and full CPU word
validation. Passing pixels establish the recipe's output, not the absence of
a redundant Vulkan completion. Use the existing Vulkan performance log to
check whether the completed case avoids a finish and whether the pending
control retains one. **This is not a reproducer for xemu #366's equality
boundary:** C's clear advances the recording epoch before starting its
command buffer on the parent too. Both builds are expected to skip an
unnecessary completion for A. Native equality-boundary coverage still needs
a proven operation that starts recording without first advancing that epoch.
Counter logs cover startup and finalization too, so
totals need that limitation. Instrumented, unpaired runs are diagnostics,
not performance qualification. Existing workloads and their old timing
evidence remain separate.
