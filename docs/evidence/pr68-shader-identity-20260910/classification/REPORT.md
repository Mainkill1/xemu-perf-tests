# PR68 PGR2 Vulkan shader-identity diagnostic

Status: **complete cause classification**. This is one diagnostic run, not performance qualification.

| Identity | Value |
| --- | --- |
| xemu commit | `1ba2c59ee69c6c909bd48b63290fa753ff5fe868` |
| Git tree | `bb96e819c768384907e13f45074f8733d256ed21` |
| xemu SHA-256 | `bf4a3908bcba4d3f6f891ad3562ff1f45a2042feca6c0a244072f1b0a7df4663` |
| Parser source | `Mainkill1/xemu-perf-tests@54739778eb0d7783fee35f911c462c6f41a11132` |
| Route | PGR2 snapshot, Vulkan, B-3, 3-second warmup, 60-second measurement |
| Trace | No WPR or ETL; shader identity enabled only for the owned xemu process |

## Gameplay admission

| Metric | Result |
| --- | ---: |
| Guest frames | 1,748 |
| Average interval | 34.331 ms |
| p95 | 41.175 ms |
| p99 | 44.262 ms |
| Maximum | 59.493 ms |
| Intervals at least 75 ms | 0 |
| Host presents | 3,595 |
| Focus-loss / nonresponsive samples | 0 / 0 |

The captured image showed the expected in-race PGR2 scene. WM_CLOSE completed normally, the producer-thread shutdown hook emitted the deferred summary, the private HDD was deleted, and the immutable seed remained unchanged.

## Identity result

| Stage | Misses | First source | Different key, same source | Same-key repeat | Unique keys | Unique sources | Compile sum / max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Vertex | 72 | 56 | 16 | 0 | 72 | 56 | 275.939 / 7.013 ms |
| Geometry | 5 | 4 | 1 | 0 | 5 | 4 | 8.927 / 1.867 ms |
| Fragment | 64 | 61 | 3 | 0 | 64 | 61 | 178.553 / 4.110 ms |
| **Total** | **141** | **121** | **20** | **0** | **141** | **121** | **463.419 / 7.013 ms** |


The trace is complete and unsaturated: 141 records, 121 unique stage/source identities, and `records_saturated=0`. Twenty misses (**14.18%**) used a different state key for GLSL already seen in the same stage. They consumed 68.200 ms of glslang time and 75.219 ms across all four measured phases. No identical key was recompiled.

## Primary slow phase

The run's worst interval was guest frame 673. Shader identity uses the immediately preceding profile-frame number; every burst overlapping the measured log follows that `N` to `N+1` mapping.

| Measurement | Result |
| --- | ---: |
| Guest interval | **59.493 ms** |
| Pipeline preparation | **43.738 ms** across 4,808 calls |
| Draw flush | 53.172 ms |
| Shader misses at profile frame 672 | 2 vertex + 2 fragment |
| First / duplicate sources | **4 / 0** |
| GLSL generation | 0.797 ms |
| glslang compilation | **18.217 ms** |
| Vulkan module creation | 0.043 ms |
| Reflection | 1.269 ms |
| Four measured shader phases combined | **20.326 ms** |

## Implication

The diagnostic confirms both optimization routes have distinct scope:

- Canonicalizing shader compilation keys or reusing exact stage/source artifacts can eliminate 20 observed redundant recompiles. Vertex state accounts for 16 of them.
- The primary hitch consists entirely of four first-seen sources. Same-process source deduplication cannot remove that specific burst. Persisted SPIR-V or prewarming a previously observed workload can move its 18.217 ms of glslang work off the draw path.
- Module creation totaled only 1.367 ms across all 141 misses. Key hashing or Vulkan module creation is not the dominant measured cost; glslang totaled 463.419 ms.

No average-FPS improvement, warm-cache result, baseline comparison, or product acceptance is claimed.

## Files

- `run-summary.json`: sanitized machine-readable result and limitations.
- `shader-identity-summary.json`, `.csv`, and `.md`: exact outputs from the pinned parser.
- `frame-stage-attribution.csv`: per-frame/per-stage identity classes, timing, and measured-frame linkage.
- `SHA256SUMS.txt`: portable evidence hashes.
