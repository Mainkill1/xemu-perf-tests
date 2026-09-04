# Report-query workload

`ReportQuery` is the correctness and timing gate for NV097 ZPASS report
completion. It validates report memory directly. Every leaf establishes its
own ZPASS and report-DMA state, writes sentinels into dedicated uncached DMA
targets, queues a terminal GPU semaphore after its last report, and validates
timestamp, value, and done only after that semaphore completes.

The suite covers report ordering and DMA-target ownership through:

- a report with ZPASS explicitly disabled;
- one counted draw and report boundary;
- a clear between two equal counted draws;
- two cumulative report boundaries;
- changing `SET_CONTEXT_DMA_REPORT` with an older report pending;
- producer work and another draw queued after the first report boundary;
- rewriting the same RAMIN descriptor while its report is pending;
- placing a report where its offset is in range but the complete 16-byte record is not.

Counted-draw assertions are relational rather than tied to one renderer's
rasterization constant: the first count must be nonzero, equal draws separated
by a clear must match, and cumulative equal draws must double. A published
record must also replace the timestamp and value sentinels and contain the
expected zero `done` field. This keeps the core ordering oracle useful on xemu
and physical Xbox hardware while detecting early, dropped, reordered,
partially written, or mis-targeted reports.

## Descriptor-rewrite oracle

The descriptor-rewrite leaf first publishes a positive-control report to A0.
It then resets A1, B0, and B1, queues delayed counted work and the tested report
to A1, immediately rewrites the same RAMIN descriptor from the guest CPU to
target B, and queues a post-rewrite control report to B0. After a terminal
semaphore completes, A1 must contain a complete report, B1 must retain all
three sentinels, and B0 must contain a complete report. The exact four original
RAMIN descriptor dwords are restored after completion.

The A0/A1/B0/B1 layout makes every control and tested destination distinct.

This leaf has no artificial sleep and does not reuse the A0 positive-control
destination for the tested report. It is a correctness-only, xemu-only oracle
until physical-hardware descriptor ownership is characterized; its elapsed
time must not be used as a performance metric.

## DMA-range oracle

The range-guard leaf uses a larger test-owned backing allocation with an
intentionally short inclusive DMA limit. A valid report at offset 0 is the
positive control. The invalid report begins at offset 16: its starting byte is
within the limit, but its complete 16-byte record is not. Eight bytes before,
the full target record, and eight bytes after are filled with canaries and must
all remain unchanged after terminal completion.

This is also a correctness-only, xemu-only fault oracle pending physical
hardware characterization. It executes once per selected run and is excluded
from performance interpretation.

## Results and cleanup

Each result stores structured report observations for A0, A1, B0, and B1,
terminal-semaphore completion, performance eligibility, and range-canary
status. These fields make failures diagnosable without relying on a framebuffer
hash alone.

Before freeing report memory, teardown disables ZPASS, binds the normal full-RAM
DMA context as the safe report target, restores the exact original RAMIN
descriptor, queues and waits for a terminal semaphore, and then waits for the
GPU. A failing correctness-only leaf is not repeatedly profiled.

Any optimization that defers report completion must pass all eight leaves, the
full XISO suite, Vulkan validation, and bounded resource-lifetime checks before
retail snapshot confirmation.
