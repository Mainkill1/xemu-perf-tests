# PFIFO packet-boundary hardening tests

`PFIFOPacketBoundary` is an xemu-only correctness suite. It deliberately
reaches xemu's private `NV2A_MAX_BATCH_LENGTH` limit and must not be run on physical Xbox hardware. It is not a performance benchmark.

The three boundary leaves cover `NV097_ARRAY_ELEMENT16`,
`NV097_ARRAY_ELEMENT32`, and `NV097_INLINE_ARRAY`. Each leaf fills the relevant
destination to one value below capacity, submits a batch that crosses the
limit, then submits the exact-capacity tail and one further word before
resetting primitive state. An old-head negative control terminates at the
crossing batch. A repaired build must remain usable, recover its primitive
state, and produce its fixed framebuffer hash. The guest does not read xemu's
private destination state, so these leaves do not establish whether a rejected
packet was atomically discarded; that internal invariant needs an xemu-side
unit test or trace probe.

`pfifo.incrementing-inline-fallback` starts an incrementing command at
`NV097_INLINE_ARRAY`. The inline handler must consume one word, allowing the
next word to reach the following incremented method. This validates the
incrementing fallback independently from the non-incrementing bulk path.

For the scalar trace fallback, run the same leaves with
`nv2a_pgraph_method_abbrev` enabled. Enabling that trace event selects the
production scalar path while avoiding a full trace line for every repeated
method. Compare its result records and a test-only method-decision probe with
the ordinary bulk run.

The four leaves have five-minute per-test timeouts because their boundary
setup submits up to 524,286 words. Their one-iteration durations are diagnostic
only and cannot support performance claims.
