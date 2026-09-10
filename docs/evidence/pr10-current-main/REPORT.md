# PR #10 current-main qualification

Atomic oversized-packet handling passes its focused correctness, scalar/bulk equivalence, validation, and accepted-packet performance gates. The full 154-record suite reaches every record on both renderers. OpenGL's only failure reproduces the range corruption tracked by Mainkill1/xemu#60. Vulkan's only failure is the same test ID, but its canaries remain intact and its separate publication-fence B0 positive control fails; it does not reproduce the OpenGL overwrite.

## Accepted-packet performance

Positive Improvement % is favorable; `+bad` means a lower raw time is better.

| Renderer | Workload | Metric | Raw + | Previous main | Candidate | Improvement % | Gate |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| Opengl | array_element16 | mean run average | `+bad` | 522.000 us | 522.000 us | +0.000% | PASS |
| Opengl | array_element16 | mean run p95 | `+bad` | 525.000 us | 524.500 us | +0.095% | PASS |
| Opengl | array_element32 | mean run average | `+bad` | 1,144.500 us | 1,129.000 us | +1.354% | PASS |
| Opengl | array_element32 | mean run p95 | `+bad` | 1,151.500 us | 1,135.500 us | +1.389% | PASS |
| Vulkan | array_element16 | mean run average | `+bad` | 1,704.500 us | 1,681.000 us | +1.379% | PASS |
| Vulkan | array_element16 | mean run p95 | `+bad` | 1,725.500 us | 1,705.500 us | +1.159% | PASS |
| Vulkan | array_element32 | mean run average | `+bad` | 2,511.500 us | 2,434.500 us | +3.066% | PASS |
| Vulkan | array_element32 | mean run p95 | `+bad` | 2,517.000 us | 2,437.500 us | +3.159% | PASS |

## Correctness

| Check | OpenGL | Vulkan |
| --- | --- | --- |
| Focused bulk boundaries | 4/4 PASS | 4/4 PASS |
| Scalar fallback boundaries | N/A | 4/4 PASS; invariants identical to bulk |
| Validation | N/A | Active; 0 unique VUIDs in bulk and scalar cells |
| Full XISO | 154 records; only `dma_range_guard` fails; canaries changed (#60) | 154 records; only `dma_range_guard` fails; canaries intact, B0 publication fence fails; 0 VUIDs |

Boundary timings are correctness-only. The accepted-packet rows use two runs per role in B1-C1-C2-B2 order and enforce at least 15 seconds of measured work plus 5 seconds of warmup per cell.
