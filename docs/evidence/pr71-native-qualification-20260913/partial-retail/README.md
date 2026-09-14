# PR #71 integrated-head retail capture: partial results

The integrated `4f0a8797` campaign was stopped after two completed PGR2 fresh/full-start OpenGL cells at the owner's request to avoid further repeat testing. Both cells passed gameplay/measurement admission, closed normally, and removed their private disks. The third cell was interrupted and is **excluded**. The campaign receipt is therefore `failed` with successful final cleanup; this is an intentional interruption, not a candidate regression. Its last orphan PresentMon ETW session was closed.

The comparison uses the fixed cycle baseline `9f618d6d` (executable SHA-256 `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b`) and PR #71 candidate `4f0a8797` (executable SHA-256 `773c9428c4013437f755f03c1adbd7e36b46358accfaf5b50a5ef81dc2cb28ff`). Both used the same PGR2 fresh-start seed SHA-256 `8b4f7c81be6ece5db3fc98d683d86d0515db43b2447e8dff14bfd9b45078c606`, isolated portable profiles, OpenGL, default-Off hybrid and shortcut settings, and a 120-second stationary start-line capture. The maintained full XISO revision and complete per-test metrics are [published separately](../integrated-xiso/).

| PGR2 full start, OpenGL | Baseline | Candidate | Candidate improvement |
| --- | ---: | ---: | ---: |
| Average FPS (higher is better) | 30.000371 | 29.999951 | -0.001% |
| Mean guest interval (ms) | 33.332849 | 33.333327 | -0.001% |
| p95 guest interval (ms) | 33.599 | 33.629 | -0.089% |
| p99 guest interval (ms) | 35.028 | 33.995 | +3.039% |
| Maximum guest interval (ms) | 39.766 | 34.746 | +14.448% |
| Guest frames | 3,602 | 3,603 | workload count |
| Host presents | 7,196 | 7,196 | workload count |

Improvement is `(candidate/reference - 1) × 100` for FPS and `(reference/candidate - 1) × 100` for intervals. This single capped, stationary OpenGL pair cannot establish a Vulkan ubershader performance benefit. There is no completed exact-head previous-main, Vulkan PGR2, or Morrowind retail comparison in this stopped campaign. Earlier retail results under `results-r1/` belong to the older `e6048469` product head and must not be presented as exact-head qualification.

The complete retained cell receipts are `retail/cells/01-pgr2_full_start-baseline-opengl.json` (SHA-256 `61cff3e8cd7df8c4f8b70ab57f1806d88ac96a4e4504f8e9ea1baeef37e6ae3c`) and `retail/cells/02-pgr2_full_start-candidate-opengl.json` (SHA-256 `b1a9e387d8c73168e9496628e127b2871702cab28bf33cc75128b3a22638c2af`) in the controlled test-host capture. Raw captures and portable profiles remain there; the table above is the publishable result without host-local paths or raw personal-system details.

The **current-main control build** `7a14b022` (SHA-256 `a2c5445474daf63e6fc49e3d28698bb8fce95911e96c51d0005a8ba15793f6f1`) deliberately has no ubershader switch. The **candidate build** contains `Vulkan ubershader` in Machine → Settings → Advance Performance → Vulkan; it is default Off and requires a restart after changing it. A separate `Skip unchanged shader work` switch is live-switchable and default Off.
