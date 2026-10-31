# R6G5B5 unsigned cubemap contract

Revision 2 of `texture_cubemap_fallback.bordered_r6g5b5_size1`, `size2`,
`size4` and `size8` checks unsigned R6G5B5 decoding. The previous revision
explicitly reproduced xemu's signed conversion and allowed a one-unit RGB565
tolerance. It cannot establish correctness of the unsigned format repair.

Packed input words and expected RGB bytes are literal known answers:

| Packed word | R | G | B |
|---|---:|---:|---:|
| `0000` | 0 | 0 | 0 |
| `ffff` | 255 | 255 | 255 |
| `fc00` | 255 | 0 | 0 |
| `03e0` | 0 | 255 | 0 |
| `001f` | 0 | 0 | 255 |
| `8210` | 130 | 132 | 132 |
| `7ceb` | 125 | 57 | 90 |
| `0001` | 0 | 0 | 8 |

Red occupies bits 15–10, green 9–5 and blue 4–0. Widening repeats the
component's high bits into the low bits. Samples require exact RGB565
quantization of these literal colors and alpha 255; no signed normalization
or tolerance applies. The eight-color cycle also preserves horizontal texel discrimination with the
existing `x * 7` source pattern. Validation remains outside the timed draw body.

The unsigned interpretation is documented in [upstream xemu's format
repair](https://github.com/xemu-project/xemu/commit/03b988c9d76553b33ed712ba00822ffdf49f0e7d),
which links its Xbox test and hardware images. These tests have not been newly
executed on physical Xbox hardware. They retain their `xemu-only` target because
the surrounding border and raw LOD-clamp contract remains emulator-specific.

The new eight-color payload changes the source FNV32 known answers. A separate
host Morton-layout generator checks all four values. Four stable IDs and their
legacy names remain, while their revisions become 2 and the catalog identity
changes. Generated plans therefore bind the new catalog; revision-1 pixel
hashes and payload hashes must not be reused or relabeled as revision-2 proof.
Palette, RGBA8 and DXT1 controls retain their revisions and source bytes.

For emulator qualification, run the four affected leaves and corresponding
RGBA8 controls on matched GL/Vulkan builds at 1x and 4x, retain all internal
oracle failures, and compare game rendering, frame cadence/tails and resource
use. A parent with the old signed conversion is expected to fail the unsigned
oracle. No new expected framebuffer hash may be inferred solely from stable
candidate output. Source/catalog binding and passing host contracts do not
establish runtime correctness or a speedup.
