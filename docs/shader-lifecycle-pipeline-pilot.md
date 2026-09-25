# Shader lifecycle pipeline pilot

This is the first executable slice of the PR #43 design. It holds shader,
texture, geometry, target, and vertex-format identity fixed while generating 17
legal full-pipeline identities: all 15 legal NV2A source-blend factors and two
additional blend-equation variants. Color-write masks are held fixed because
xemu implements them as dynamic state, so changing only the mask does not
create a distinct fixed-pipeline recipe. The audited xemu pipeline-job capacity
is 16, so the separate C-1, C, and C+1 launches request 15, 16, and 17
identities.

The guest has six independent launch plans. `pipeline.train` populates the
shader-module cache and fallback-family history. After a clean xemu process
restart, run exactly one capacity plan with Prewarm enabled and lifecycle tracing
enabled. `pipeline.identical-replay` repeats the same bytes in process;
`pipeline.uniform-only` changes visible diffuse inputs without changing the
structural pipeline key.

Guest completion, a visible image, 17 requested variants, or background worker
activity does not prove promotion. The C+1 promotion qualification passes only
when the matching xemu trace is complete and reports `pipeline-promotion > 0`.
The trace must also report an effective queue capacity of 16; otherwise the
C-1/C/C+1 labels are stale and the run is ineligible.

Run deterministic correctness and queue-path coverage on both Windows and
Steam Deck/Linux. Report latency distributions per host; they are never pooled
or averaged across the two machines. Diagnostic worker gates may be used to
prove ordering and promotion, but any run with a gate enabled is ineligible for
performance acceptance. Retail PGR2 performance qualification remains
Windows-only.
