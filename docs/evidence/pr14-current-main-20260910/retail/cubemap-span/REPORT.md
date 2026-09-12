# PR14 clamped-cubemap span attribution

Research PR #67 added opt-in counters without changing texture or rendering
decisions. The exact Windows Release build used source
`866bba7971427c7dfe3bb6b193bc9760b93985c2`, tree
`b20500d04bf7b5c061e295d954df064c26b8b0bf`, and executable SHA-256
`ff2a6b25bf4de8342ad29b7882a75eb66ff61a195ffdd58947b73fd3c990ef9f`.
Its texture-layout unit executable
`2f9638a13eaca049944e64ff9de6d1baa301c6f4c88d0e6cc07f968d433be4a5`
passed all 7 tests on the Windows test host.

The PGR2 snapshot diagnostic used Vulkan, the existing B-3 input route, a
three-second warmup, a 60-second measurement, and all optional performance
controls disabled. The order was PR14, PR67, PR67, PR14. Both builds enabled
Vulkan telemetry, so these timings are diagnostic and cannot qualify
performance.

## Frame result

Positive Improvement % is favorable. Interval metrics are `+bad`.

| Metric, median of two | Raw + | PR14 | PR67 counters | Improvement % | Use |
| --- | --- | ---: | ---: | ---: | --- |
| Average interval | `+bad` | 34.548 ms | 34.453 ms | +0.28% | Diagnostic |
| p95 | `+bad` | 41.431 ms | 41.212 ms | +0.53% | Diagnostic |
| p99 | `+bad` | 46.475 ms | 45.401 ms | +2.31% | Diagnostic |
| Global maximum | `+bad` | 73.841 ms | 61.618 ms | +16.55% | Diagnostic; one PR14 maximum was outside the target phase |
| Phase peak, indices 150-160 | `+bad` | 59.723 ms | 61.618 ms | -3.17% | Diagnostic counter overhead/variance; no speed claim |

Every cell completed the expected gameplay and cleanup checks. The first PR14
cell recorded one interval above 75 ms at measured-frame index 631; the other
three cells recorded zero such stalls. This isolated global maximum is not the
phase being investigated.

## Focused counter result

| Scope | PR67 run 1 | PR67 run 2 | Finding |
| --- | ---: | ---: | --- |
| Full telemetry frames | 2,322 | 2,311 | Complete records before the allowed partial final write |
| Measured telemetry frames | 1,744 | 1,739 | Exact 60-second windows |
| Clamped cubemap prepares, full run | 0 | 0 | Path absent |
| Clamped cubemap prepares, measured window | 0 | 0 | Path absent |
| Storage/sample extra span bytes | 0 | 0 | No enlarged span was checked or hashed |
| Focused surface/dirty/hash/upload CPU time | 0 us | 0 us | No attributable cost |

The suspected PR14 path requires `cubemap && storage_levels > levels`. It did
not execute once in either full process lifetime. The clamped-cubemap storage
span therefore cannot cause the PGR2 tail spike. This rejects the proposed
enlarged surface-range, dirty-check, and hash-span explanation for this route.

## Decision

PR14 remains held because its ordinary uninstrumented phase-peak median still
fails at -20.78% Improvement. This diagnostic narrows the cause: do not build a
sampled-prefix hash optimization for PGR2, because the prerequisite path is
absent. The next bounded check must establish whether any cubemap path executes
and measure its total cost; if that is also absent or below 1 ms, isolate the
PR14 Vulkan layout changes from the OpenGL-only repair in separate builds.

`summary.json` contains the compact machine-readable identities, frame rows,
and zero-counter result. Multi-megabyte telemetry JSONL and screenshots remain
outside Git history.
