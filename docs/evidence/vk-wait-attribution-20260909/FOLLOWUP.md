# Rejected capture follow-up

Source review established why normal close produced only a schema: QEMU normal
cleanup enters VM shutdown without unrealizing the NV2A device. The deferred
logger's renderer-destructor call was therefore unreachable on that exit path.
[Repair f16292b4](https://github.com/Mainkill1/xemu/commit/f16292b472e6bf5aa9d4448cbbf352bc13131b06)
invokes the existing idempotent perf finalizer from Vulkan's
`pre_shutdown_trigger`, after PFIFO acknowledges idle and while the producer
locks remain held. It changes one executable call; no per-frame write or
synchronization policy is added. Independent review approved the repair for a
diagnostic experiment. The old native/build result does not qualify this new
source. Build and normal-close telemetry validation remain required.

A subsequent host-health check found a stale PowerShell helper from an earlier
recursive status query. It held an 11,396,313,088-byte working set. Its exact
identity and originating command established ownership before it was stopped.
Available physical memory increased from 602,304,512 to 12,270,919,680 bytes.
WPR was idle; no workload, recorder, exporter, analysis process or owned ETW
session remained after cleanup. The shared GUI server, unrelated sessions and
saved traces were preserved. [Sanitized observations](host-cleanup.json)
retain byte units and timestamps. These are later host-health observations;
they do not measure or explain a specific gameplay slowdown.

Future admission/cleanup checks include launcher and status-query helpers as
well as trace tools. Use bounded direct-path queries, retain child identities,
and verify that a client timeout did not leave remote work running. The
original failed capture remains rejected and preserved without replay.
