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

The C-1/C/C+1 variant draws are side-effect-free: color writes, depth/stencil
writes, and queries are disabled so Continue may safely omit a not-yet-ready
pipeline under xemu's conservative policy. A separate unblended visible sentinel
is drawn afterward and validated, while every variant tile must retain the known
background color. This keeps the framebuffer oracle meaningful without making
the queue test depend on replaying an omitted resource-producing draw.
The C+1 case uses two immediate passes. The second pass revisits every capacity
identity while a deliberately delayed background job may still be
pending. Promotion still must be established from the matching host trace.

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

## Visible learned-fallback readiness profile

The first acceptance gate for the reduced xemu #203 implementation is a small
**visible, non-omittable readiness profile**, not the capacity/promotion
campaign above. It renders three canonical fallback families using triangles,
triangle strips, and quads. Each family uses two output-equivalent combiner
programs whose specialized fragment identities differ while their compatible
fallback combiner state canonicalizes to the same family. Every draw writes a
required color tile, and every tile is checked; no sentinel or unchanged
background can substitute for the shading output.

Run `readiness.train-visible`, exit xemu cleanly, and restart with the same
learned history and effective Vulkan, Prewarm, and shader caching settings.
Before each focused replay, selectively remove only the owned test-cache
artifact named in the run manifest. Use separate replays for a missing vertex,
missing geometry, and missing fallback fragment artifact. Never delete or
claim control over a user's host-driver cache.

For `readiness.replay-visible`, acceptance requires fallback pipeline publication before first demand
and actual submitted use of that exact full pipeline.
The trace must then distinguish the first correct specialized use from the
earlier correct fallback output. Module publication without a complete
pipeline, a complete pipeline never used by a submitted draw, or correct final
pixels without lifecycle ownership is insufficient.

`readiness.identical-replay` uses a bounded two-second inter-pass lead interval:
the first pass must use the ready learned fallback, and the second must prove
actual specialized-pipeline takeover after publication. This interval makes the
case a mechanism diagnostic, not a performance result. Identical replay and
`readiness.uniform-only` must produce no new structural compiler work once the
trained identities are ready. The separate
`readiness.early-demand` plan runs with empty history and no preparation lead
time; it must remain explicitly uncovered rather than being relabeled as a
prewarm success.

This mechanism proof does not require a promotion event because it changes no
queue or scheduling policy. Keep the C-1/C/C+1 promotion workload as an
independent diagnostic. Run the visible readiness profile on Windows and Steam
Deck/Linux, retain each host's evidence separately, and make no performance
claim from fault-injected or diagnostically delayed runs.
