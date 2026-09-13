# Vertex-stack build and integration audit

The #85 → #87 → #89 Git ancestry and GitHub PR bases match the intended
stack. Current `main` (`9148241d`) and the retained control source
(`6bf9e98c`) have the same complete Git tree, `2301f1cc`. The measured
control executable SHA-256 is `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6`.

| Role | Git head | Git tree | Measured executable SHA-256 |
| --- | --- | --- | --- |
| #85 | `8d9245ddeb5f13d23a5e3f2aafdb5144c4bdad30` | `4330ee6b527dc43b910d0038476f50c26b6b4267` | `0c0e11d66e5a2b0b75fad38c8bb5acf88b5291b1115a47c6ba501f262fce313d` |
| #87 | `3fa5a650e108c12d2106a43450f375fefb5ddf6e` | `6fe4be95a1f38a19c67005023b059169d77f03ab` | `ea6d5dc552d71817bd7acc9ad025420ac2d087031b69c2cebd3f944db1995ed0` |
| #89 | `7a159370143566e723cccd8b2ab5018b3b9d70df` | `a19c01fdb566ddd62536ae983be185714f4d964b` | `f2317a7ac7eb1009ccf9788ad76c6ed4c2dc9bdc0b6df986b5828eebb9e405dc` |

The staged executable bytes match these hashes. The build logs show that
the changed Vulkan C translation units, including `buffer.c`, `draw.c`,
`renderer.c`, `surface.c`, and `vertex.c`, were compiled before each link.
The #89 log also shows both policy-test objects compiled. Inspection of
the control and #89 PE/DWARF producer records shows the same GCC 16.1.0,
`-O2`, `-g`, LTO, and x86-64-v3 feature flags. The control's manifest calls
this profile “Release”; the candidate build configuration calls it
`buildtype=debug`, `optimization=2`, `debug=true`, `b_lto=true`. Those labels
describe **comparable emitted optimization settings**, not a verified
release-versus-debug optimization mismatch.

The candidate builder used a checked-out historical parent plus source-file
overlays rather than checking out each candidate Git commit. Every file in
the #85/#87/#89 overlay archives matches the corresponding Git head. The
#89 archive contains all 12 files changed from its overlay parent and no
deletions; the #87 and #85 archives cover their changed runtime files when
applied in the recorded build order. The retained builder source after the
last (#85) build also passes a SHA-256 check against **every regular tracked
file** at the exact #85 head. The original build procedure recorded hashes
of overlaid files, but did not record a whole-tree source digest at each
link. Thus the available records find **no wrong code or compiler flags**,
while they do not provide a complete per-binary source attestation. A future
qualification build should check out each exact head in an isolated source
directory, verify the complete tree before compilation, and record the
compiler command/flags and final executable hash.

The two-order PGR2 snapshot comparison [below](results/pr85-pgr2-snapshot-abba.json)
shows #85 p95 and p99 worse than the main control in both orders. This is a
performance hold, independent of the misleading build-profile labels. It
does not establish which #85 operation is responsible. The new per-sync
surface-overlap scan and early surface download are source-level places to
measure, without weakening the required surface-before-CPU-decode ordering.
