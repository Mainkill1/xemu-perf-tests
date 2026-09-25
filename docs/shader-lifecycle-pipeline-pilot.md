# Visible learned-fallback readiness profile

This is the focused executable slice used to validate learned fallback-family
readiness. It intentionally excludes the separate C-1/C/C+1 capacity and
promotion campaign because xemu PR #228 does not change queue capacity or
scheduling.

The suite renders three canonical fallback families using triangles, triangle
strips, and quads. Each family uses two output-equivalent combiner programs
whose specialized fragment identities differ while their compatible fallback
combiner state canonicalizes to the same family. Every draw writes a required
color tile, and every tile is checked; no sentinel or unchanged background can
substitute for the shading output. This is therefore a visible, non-omittable
readiness profile.

Run `readiness.train-visible`, exit xemu cleanly, and restart with the same
learned history and effective Vulkan, Prewarm, and shader caching settings.
Before each focused replay, selectively remove only the owned test-cache
artifact named in the run manifest. Use separate replays for a missing vertex,
missing geometry, and missing fallback fragment artifact. Never delete or
claim control over a user's host-driver cache.

For `readiness.replay-visible`, acceptance requires fallback pipeline
publication before first demand and actual submitted use of that exact full
pipeline. The trace must then distinguish the first correct specialized use
from the earlier correct fallback output. Module publication without a complete
pipeline, a complete pipeline never used by a submitted draw, or correct final
pixels without lifecycle ownership is insufficient.

`readiness.identical-replay` uses three identical passes with a bounded
two-second interval between them. The first pass must use the ready learned
fallback. If an exact stage was absent after restart, the second pass may be
the first demand able to queue its complete specialized pipeline; the third
must prove actual specialized takeover after publication. These intervals make
the case a mechanism diagnostic, not a performance result. Identical replay and
`readiness.uniform-only` must produce no new structural compiler work once the
trained identities are ready.

The separate `readiness.early-demand` plan runs with empty history and no
preparation lead time. It must remain explicitly uncovered rather than being
relabeled as a prewarm success.

Every readiness route holds its validated result display for ten seconds after
the measured guest work. This bounded, unmeasured window lets unattended host
captures retain the actual colored tiles and result overlay instead of a later
menu screen.

This mechanism proof does not require a promotion event because it changes no
queue or scheduling policy. Run it on Windows and Steam Deck/Linux, retain each
host's evidence separately, and make no performance claim from fault-injected
or diagnostically delayed runs.
