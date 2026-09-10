# PR14 matched worst-frame trace checkpoint

The matched trace reproduced the PR #14 hold at the same measured guest frame.
Previous main completed frame 676 in 63.563 ms; the candidate took 74.741 ms.
That is **-17.59% Improvement** for maximum interval and fails the independent
tail gate.

Both cells used the same PGR2 snapshot, Vulkan renderer, B-3 input route,
three-second warmup, 60-second measurement, and disabled optional performance
controls. The executable was the only changed input. Each startup trace carried
the correct process/image identity and reported zero lost events and buffers.

## Exact result

Positive Improvement % is favorable. All interval, run-time, wait-time, and
ready-time metrics below are `+bad`.

| Metric | Raw + | Previous main | Candidate | Improvement % | Gate |
| --- | --- | ---: | ---: | ---: | --- |
| Frame 676 interval | `+bad` | 63.563 ms | 74.741 ms | **-17.59%** | **FAIL** |
| PFIFO running in frame | `+bad` | 50.456 ms | 50.843 ms | -0.77% | PASS |
| PFIFO blocked in frame | `+bad` | 12.974 ms | 23.649 ms | **-82.28%** | INVESTIGATE |
| PFIFO ready delay in frame | `+bad` | 0.133 ms | 0.249 ms | -87.22% | Context |
| Longest PFIFO blocked interval | `+bad` | 3.663 ms | 10.480 ms | **-186.09%** | INVESTIGATE |

PFIFO spent only 0.387 ms more running in the candidate frame. It spent 10.675
ms more blocked, which accounts for nearly all of the 11.178 ms frame
difference. The 10.480 ms candidate interval was a condition wait for emulated
work. CPU 0/TCG woke PFIFO and the thread then ran after 0.0048 ms of ready
delay. This excludes Windows scheduler starvation for that interval. The wait
was also distinct from a Vulkan GPU fence wait.

## Code attribution

This trace does **not** identify a slow PR #14 function. No sampled leaf in
`create_texture()`, `upload_texture_image()`, `get_texture_layout()`,
`pgraph_get_texture_length()`, the dirty/surface checks, or the new shared
cubemap helper occurred inside either exact frame. Candidate hash weight was
about 1.000 ms, while previous-main hash weight was about 3.059 ms. That result
does not support the proposed enlarged-hash-span explanation for this frame.

Both builds performed Vulkan shader/pipeline compilation during frame 676.
The candidate's long PFIFO wait ended when CPU 0/TCG called a PFIFO wake path,
but the MinGW wake stack did not resolve to the exact MMIO caller. The evidence
therefore supports the tail failure and its producer-wait location; it does not
support naming PR #14 texture code, shader compilation, or the host scheduler
as the cause.

## Decision and next gate

PR #14 remains draft and held. It cannot be described as faster or performance
neutral while this repeated maximum regression remains unresolved.

The next admitted test uses the existing opt-in per-frame Vulkan telemetry on
the same unchanged executables and route. It compares pipeline preparation,
texture binding/upload, queue submissions, and fence waits without collecting
another ETL. If that result still cannot tie the frame to a changed path, the
shared storage-level accounting and the renderer repairs must be instrumented
or built as separate one-change candidates and tested independently.

The multi-gigabyte ETLs remain outside Git history. Their SHA-256 identities,
sizes, zero-loss status, exact build identities, and compact attribution result
are recorded in `attribution-summary.json`.
