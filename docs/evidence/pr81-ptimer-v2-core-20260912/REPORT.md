# PR #81: PTIMER scheduling replacement — correctness admitted, performance held

**Product PR:** https://github.com/Mainkill1/xemu/pull/81
**Tracking issue:** https://github.com/Mainkill1/xemu/issues/73
**Previous main:** `9148241de690617ac0a21a26b41858585c1e3cab`
**Fixed cycle baseline:** `9f618d6d8c4c446ef023955f3d4de22f661f61a4`
**Tested candidate:** `98f1a7a49cb7a6ccb8feba20438dc86f9ead58d5`

The exact candidate built as the Windows x64 product with GCC 16.1.0, `-O2`, debug symbols, full LTO, and x86-64-v3 options. Product executable SHA-256: `5da6b82f13b6ddc325972eabecb4144b72d7930c46514def369f8d4da1c050bf`. The Windows-targeted PTIMER unit executable SHA-256: `66ae231829f089e37fb4abf97c41a164032f2c80f38d2bbba72f65ae6f5ee6db`.

| Check | Expected | Observed | Status |
| --- | --- | --- | --- |
| Windows product link | Exact candidate links | Linked with the production toolchain | PASS |
| Production PTIMER translation-unit fixture under Wine | 75 cases pass | 75/75, no failed cases | PASS |
| Repeated enabled ACK, future alarm | No extra timer modification/deletion | 1,000 ACKs produced no extra queue API calls | PASS in fixture |
| Repeated masked ACK, absent host timer | No repeated deletion | 1,000 ACKs produced no extra deletion requests | PASS in fixture |
| Overdue ACK, callback consumption, restore | Reconcile/rearm/reconstruct | All focused cases passed | PASS in fixture |
| Native Windows game/snapshot behavior | PGR2 snapshot/full and Morrowind active scene | 18 admitted retail cells across Vulkan/OpenGL, including matched previous-main controls | PASS for tested behavior |
| Full 159-record XISO, both renderers | No new candidate failures | Candidate Vulkan 158 PASS / 1 inherited FAIL; OpenGL 157 PASS / 2 inherited FAIL; matching previous-main OpenGL control | PASS for incremental correctness; suite overall FAILED |
| Paired fixed-work performance | No >2% adverse regression | OpenGL Morrowind p99 adverse by 2.521% and 2.403% in opposite run orders | **HOLD** |

The full [TAP output](ptimer-unit.tap) has SHA-256 `48d226dcab73ee6b639506238dc0d76ab1162210d35309c9d47818d4d3f5a904`. It includes the archived #59 semantic/clock-phase controls plus new idempotent-scheduling cases. The fixture compiles the production PTIMER, PRAMDAC, and scheduling-core source with deterministic clock/timer/IRQ stubs; it does **not** exercise QEMU's real timer-list locks, Windows scheduling, PCI IRQ fan-out, or actual VMState serialization.

| Performance metric | Raw + | Fixed baseline | Previous main | Candidate | Improvement vs baseline | Improvement vs previous main |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| PGR2 snapshot p99, Vulkan | `+bad` | 44.896 ms | 42.981 ms | 43.156 ms | +3.876% | -0.406% |
| PGR2 full-start p99, Vulkan | `+bad` | 34.253 ms | 33.917 ms | 33.996 ms | +0.750% | -0.233% |
| Morrowind snapshot p99, Vulkan | `+bad` | 52.773 ms | 55.114 ms | 54.760 ms | -3.765% | +0.642% |
| PGR2 snapshot p99, OpenGL | `+bad` | no matched retained value | 44.157 ms | 44.786 ms | N/A | -1.424% |
| PGR2 full-start p99, OpenGL | `+bad` | no matched retained value | 33.956 ms | 34.062 ms | N/A | -0.312% |
| Morrowind snapshot p99, OpenGL | `+bad` | no matched retained value | 40.960 ms | 41.969 ms | N/A | **-2.462%** |
| Full XISO timing | `+bad` | N/A | N/A | Excluded | N/A | N/A |

Positive Improvement % means favorable. The Vulkan fixed-baseline values are retained published references from the [PR76 report](../pr76-cross-gpu-host-copy-20260911/REPORT.md); the stable executable was not rebuilt. OpenGL has no retained baseline value proven to match this exact retail protocol, so its cumulative cells are N/A. Candidate and previous-main values are medians of the admitted same-session cells. Morrowind's rate is **NV2A display-write cadence**, not host-present FPS. The older baseline's Vulkan Morrowind deficit was already present on previous main; PR #81 improves its incremental p99 while remaining behind that fixed reference.

## Native retail qualification and hold

The Windows NVIDIA host ran 60-second PGR2 snapshots, 120-second PGR2 fresh starts, and 60-second Morrowind snapshots in both renderers. Previous-main control executable `6857240d...` was built from `6bf9e98c...`, whose runtime source tree exactly matches PR #81's parent `9148241d...`. Every admitted PGR2 cell reached the gameplay oracle, measured guest progression, had zero focus/not-responding samples and zero intervals at or above 75 ms. Every Morrowind cell reached QMP running, received Start/B, passed the final-image check, and deleted its private HDD. The Morrowind maximum intervals were independently computed from the retained guest flip timestamps; that calculation reproduced the runner's p95/p99 values exactly.

| Workload | Renderer | Pairs | Previous main p95 / p99 / max | PR #81 p95 / p99 / max | p99 Improvement % |
| --- | --- | ---: | --- | --- | ---: |
| PGR2 snapshot | Vulkan | 2 | 38.868 / 42.981 / 51.900 ms | 38.630 / 43.156 / 53.388 ms | -0.406% |
| PGR2 snapshot | OpenGL | 2 | 41.203 / 44.157 / 57.778 ms | 41.100 / 44.786 / 63.741 ms | -1.424% |
| PGR2 full start | Vulkan | 1 | 33.658 / 33.917 / 44.271 ms | 33.563 / 33.996 / 42.065 ms | -0.233% |
| PGR2 full start | OpenGL | 1 | 33.627 / 33.956 / 43.210 ms | 33.648 / 34.062 / 42.506 ms | -0.312% |
| Morrowind snapshot | Vulkan | 1 | 49.567 / 55.114 / 62.493 ms | 48.388 / 54.760 / 65.908 ms | +0.642% |
| Morrowind snapshot | OpenGL | 2 | 36.425 / 40.960 / 46.748 ms | 37.076 / 41.969 / 53.269 ms | **-2.462%** |

The two OpenGL Morrowind pairs were run candidate→previous and previous→candidate. Their p99 Improvement % values were **-2.521%** and **-2.403%**. Display-write cadence was also adverse by 2.301% and 1.464%. OpenGL PGR2 snapshot p99 changed direction between its two run orders (+0.506%, then -3.397%), and its 71.019 ms candidate maximum in the first pair did not recur in the second. These are observed associations, not attribution to PTIMER queue work. The repeated Morrowind result exceeds the 2% incremental gate, so this head is **not ready to merge**.

One initial candidate Vulkan snapshot attempt is retained in [excluded attempts](excluded-retail-attempts.csv): PresentMon lost 311,828 ETW events and wrote no CSV. The admitted matched cells used the runner's guest-frame path with PresentMon and WPR disabled. They establish guest progression and interval distributions, not host-present FPS or timer-list/wakeup causality. Reason-tagged real timer modifications, callbacks, IRQ transitions, and wait attribution remain unmeasured. Those measurements, plus a resolution of the OpenGL Morrowind hold, are needed before claiming a performance benefit.

[Per-run retail results](retail-runs.csv) · [Paired comparisons and order](retail-pairs.csv) · [Source/build/runner manifest](retail-manifest.json). Raw captures remain on the test host; this repository contains compact sanitized results rather than private game assets or writable disks.

## Full XISO correctness admission

The candidate ran the current 159-record XISO (`5269072fb1db6b1a7ca3c9679db05bce6e204a38`, ISO SHA-256 `1e2573d416949ced403426826bf4d8597949468ed117185847f47dfd97b64260`) with catalog SHA-256 `a0674f73cef85d43f1dba0ad2059b9fa076841a0f4b1084b59186cf4ffb3871e`. The exact prior-main runtime tree was represented by the previously qualified `6bf9e98cdee50fd73e936ff2bd5b485ce14ac4dc` executable, SHA-256 `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6`; its tree matches current `main`'s parent of PR #81.

| Cell | Records | PASS | FAIL | Failed cases | Functional hashes | Vulkan VUIDs |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| PR #81 Vulkan | 159 | 158 | 1 | `report_query.dma_range_guard` | PASS | 0 |
| PR #81 OpenGL | 159 | 157 | 2 | report query; `texture_cubemap_fallback.unbordered_subblock_dxt1` | PASS | N/A |
| Previous main OpenGL | 159 | 157 | 2 | Same two cases, with the same cubemap face values | PASS | N/A |

All three xemu processes exited normally. The full per-test outcomes and framebuffer hashes are in [the 159-row comparison](full-xiso-comparison.csv); source/build/runner identities and the exact failure list are in [the admission record](full-xiso-admission.json). The report-query failure is the known inherited path tracked historically by [xemu issue #60](https://github.com/Mainkill1/xemu/issues/60). The OpenGL cubemap case returned red for every sampled face in **both** candidate and previous main, while candidate Vulkan passed its face oracle; it is now tracked by [xemu issue #82](https://github.com/Mainkill1/xemu/issues/82). These failures prevent calling either whole suite a PASS. They do not show a new PR #81 failure.

The first candidate and previous-main control runs produced 154 of the catalog's 159 records because the installed runner omitted the guest's `enable_xemu_only_tests` flag. All five missing leaves were xemu-only: four PFIFO packet-boundary cases and the unbordered cubemap case. This is the existing integration gap in [xemu-perf-tests issue #10](https://github.com/Mainkill1/xemu-perf-tests/issues/10), now affecting a fifth test. A private, isolated copy of the runner enabled that flag **only for full-suite runs**; its one-line [patch](runner-optin.patch) and SHA-256 `cd51e2192bf51a5e58862b4ff5f356867119a59c95351bc3a1378994e7917558` are retained here. The original runner was unchanged. This temporary runner adaptation is correctness evidence, not a merged reusable tooling repair.

No XISO duration is used as performance evidence. Live guest markers were unavailable, the report-query case includes a timeout, and these catalog leaves mix correctness with measured workloads.
