# Report-query workload

`ReportQuery` is the correctness and timing gate for NV097 ZPASS report
completion. It validates report memory directly. Each leaf writes sentinels
into a dedicated uncached DMA target,
queues report methods, waits for guest-memory publication, and validates the
published value before recording the normal framebuffer hash.

The suite covers report ordering and DMA-target ownership through:

- a report with no active query;
- one counted draw and report boundary;
- a clear between two equal counted draws;
- two cumulative report boundaries;
- changing `SET_CONTEXT_DMA_REPORT` with an older report pending;
- producer work and another draw queued after the first report boundary.
- rewriting the same RAMIN descriptor while its report is pending;
- placing a report where its offset is in range but the complete 16-byte record is not.

Counted-draw assertions are relational rather than tied to one renderer's
rasterization constant: the first count must be nonzero, equal draws separated
by a clear must match, and cumulative equal draws must double. This keeps the
oracle useful on xemu and physical Xbox hardware while still detecting early,
dropped, reordered, or mis-targeted reports.

The descriptor-rewrite leaf creates a bounded GPU backlog, queues a report,
then repoints the same RAMIN descriptor before completion. Publication must
still use the queue-time destination. The range-guard leaf uses a larger
test-owned backing allocation with an intentionally short inclusive DMA limit;
the out-of-range record must leave the backing sentinel unchanged.

Any optimization that defers report completion must pass all eight leaves, the
full XISO suite, Vulkan validation, and bounded resource-lifetime checks before
retail snapshot confirmation.
