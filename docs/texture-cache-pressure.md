# Four-stage texture cache pressure

`pipeline_texture_switch.cache_pressure` draws 272 nonoverlapping 8x8 tiles,
with four enabled 8x8 linear ARGB textures. All four border colors change before
each draw, producing 1,088 texture/sampler identities per invocation in xemu's
current Vulkan cache. Repeat addressing makes border color irrelevant to the
expected pixels. The final combiner cycles through all four stages; tile colors
are red, green, blue, yellow. The shared drawing helper supplies all four texture
coordinates.

The test emits stage-indexed border-color methods directly and restores each
saved stage's border color explicitly. The current PBKit++ helper omits the stage
offset for that one register, so using its commit alone would change only stage
zero and would not generate the intended pressure.

No explicit GPU completion or CPU framebuffer read divides the pressure stream.
After its fence, the test checks every pixel in each tile's central 4x4 region,
including tiles rendered before and after capacity pressure. It counts mismatches
and hashes the actual checked ARGB words using little-endian FNV-1a32. The profile
includes the completion and readback checks, so its timing is end-to-end test work,
not texture upload or queue-enqueue time alone. Resource pressure is host-dependent;
passing pixels alone do not prove any particular host cache transition occurred.

`resources/texture-cache-pressure.json` selects two warmups and one measured
invocation. Its reference hashes 13,056 checked words, derived from the four color
constants, 272 tiles, 16 interior words per tile and three invocations. It is a
recipe oracle, not a captured emulator result. The test restores the 1 KiB of
modified texture bytes and all four saved stage objects after completion.

The recipe uses ordinary texture methods and can run on original Xbox hardware;
physical hardware validation has not yet been performed. Native Vulkan cache
instrumentation is required to attribute a failure or establish rollover/eviction
coverage. The expected software behavior is correct pixels without an emulator
assertion, stale texture use or corrupted later tests.
