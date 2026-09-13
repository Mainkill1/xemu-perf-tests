# Reconciled #85 → #87 → #89 stack: exact-head qualification

**Status: draft; no merge verdict yet.** The corrected stack preserves the
prior branch history through merge commits. The cache-only #85 experiment was
reverted; [its build and mixed PGR2 result](CACHE-EXPERIMENT.md) remain in the
evidence. The current #85 repair removes the redundant surface-overlap scan
and clean-overlap vertex-mirror uploads. #89 still receives an overlap signal
from the same traversal, so versioning remains disabled for surface aliases.

| Role | Exact source / tree | Win64 executable SHA-256 | Build |
| --- | --- | --- | --- |
| Current `main` control | `9148241de690617ac0a21a26b41858585c1e3cab` / `2301f1cc976f93e5a943e065c4e12e034f33869f` | `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6` | Retained tested tree |
| #85 | `0883fb63009c6cc804681cbdb39e4454b44d8456` / `8849f205571ef98454f7de7c9eaa098b1fdcfbb6` | `e9d763da0e027f9cc21b66c090e7e9199c10bd3846a49c89277c2a07bf34b17b` | PASS |
| #87 | `b3b99fb8832b658a653d53641170da3171ab2e6c` / `87118ebf6d911b9a8b12bf21caf7ac9278cf9cee` | `54b879eb2602c57504e97f2899ee73b91aa22debca4373465896a40b6d8a57e2` | PASS |
| #89 | `150d74ac5525be769e4f44ab35718eb2607a8eec` / `66a6febaf0ac60ea1749e674bace393447fe849a` | `29eac8120cce296e312ba85147109ca5d6b62755d6326d36d4c0358a44231d25` | PASS |

The candidate builds used the same pinned Win64 GCC toolchain image
`sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`
with `-O2`, full LTO, x86-64-v3, debug information, and assertions. Each
source was clean at its recorded commit. All regular tracked files were
hash-checked before and after linking (11,404 files for #85/#87; 11,406 for
#89), and changed Vulkan objects were rebuilt. Symlink identities were
inherited from the prior exact checkout; the added/repaired paths are regular
files. The test runner's optional manifest/PDB ownership flag is separate
from this independent full regular-file check and was not requested for these
captures.

The #85 fetch-span unit passed 2/2 on Win64. The reconciled #87 fetch-span
unit passed 2/2. Reconciled #89 passed fetch-span 2/2 and version-policy 3/3.
These are policy/bounds checks, not substitutes for the complete guest suite.

## #85 versus current main: PGR2 snapshot

The [four complete cells](results/pr85-direct-pgr2-abba.json) used the same
PGR2 Vulkan snapshot, clean seed, configuration hash, scale 1, 30-second
warmup, and 60-second measured window without WPR or telemetry. All reported
complete functional and measurement status, zero focus loss, zero unresponsive
samples, and zero guest-frame stalls. Positive **Improvement %** means a lower
guest-frame interval.

| Run order | Main mean / p95 / p99 | #85 mean / p95 / p99 | Mean / p95 / p99 Improvement |
| --- | ---: | ---: | ---: |
| Main → #85 | 33.750 / 38.289 / 43.300 ms | 33.721 / 38.691 / 43.100 ms | +0.08% / **-1.05%** / +0.46% |
| #85 → main | 33.764 / 38.751 / 42.858 ms | 33.825 / 38.819 / 42.944 ms | -0.18% / **-0.18%** / -0.20% |

The prior #85 head was worse than main by -2.40% and -1.22% at p95, and
-2.49% and -1.25% at p99 in opposite orders. The direct repair removes most
of that repeated adverse signal, but its new p95 remains slightly adverse in
both orders. This is **near-neutral**, not a proven standalone performance
improvement or a merge pass. PGR2 full start, Morrowind, the full XISO, and
the combined #89 comparison remain necessary for the final verdict.

## Pending exact-head gates

| Gate | Current state |
| --- | --- |
| 161-record XISO on #85/#87/#89, Vulkan and OpenGL | Running on the test host; previous-stack results do not qualify these heads |
| #89 three-generation guest oracle and version-selection observation | Pending current-head result; previous-head test passed |
| PGR2 full start/snapshot and Morrowind snapshot at #87 → #89 | Pending matched current-head cells |
| Direct #85 GPU-surface-to-vertex and #89 finish/rollover/stale-fallback tests | Pending focused guest proof |
| Cross-platform build/review | Pending |

The [previous stack report](REPORT.md) retains its historical measurements
and per-test rows. No code has been merged into `main` on the basis of this
new record.
