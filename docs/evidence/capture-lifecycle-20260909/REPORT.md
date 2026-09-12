# Capture helper controls and memory cleanup

The exact [helper draft #9](https://github.com/Mainkill1/xemu-perf-tests/pull/9)
passed its standalone synthetic controls once under PowerShell 7.6.5. Source
`8baac6af9a7d980f8ee449c6bc3cc783690c15a9`, tree
`20a588366a559f47f02d07da188b21c947f61faf`. No game, GUI connection or trace
capture was needed. [Results and source hashes](results.json) pin the command
and observed success output. The test's owned temporary fixture and helper
were cleaned up.

The controls cover immutable clock-anchor files, post-save failures and repeat
writes; canonical closed launch layouts and invalid state/path/artifact cases;
Vulkan's required telemetry versus OpenGL's inapplicable telemetry; and null,
empty and nonempty process-query results. This qualifies those helper contracts,
not the surrounding launcher, clock precision, gameplay or performance.

A simultaneous memory admission check found a separate stale artifact-reader
helper from earlier collection work. It had tried to serialize raw PowerShell
content objects and held 56.03 GB of private committed memory with an 11.24 GB
working set. Process identity, caller and absence of descendants were checked
before cleanup. Its window-close request failed; guarded termination then
exited it. Available physical memory recovered from 0.55 GB at that observation
to 14.01 GB. WPR stayed idle, named workload/recorder/exporter processes were
absent, and the shared GUI session was preserved. Full private commands and
host process listings are excluded from this packet.

Collectors must use explicit scalar records or copy files, retain owned-helper
identities, and check termination after a client timeout. A disconnected client
does not prove the remote helper stopped. Future native runs still need bounded
before/after memory and recorder/helper cleanup checks. This cleanup is separate
from the earlier stale-helper incident and does not rewrite its saved report.

[Issue #8](https://github.com/Mainkill1/xemu-perf-tests/issues/8) remains open:
callers must persist completion independently from validation, save anchors
before fallible checks, restore environment values and record cleanup failures.
The earlier Vulkan anchors remain lost. Neither a baseline rebuild nor an XISO
suite change occurred.
