# PR #81: PTIMER scheduling replacement — focused admission

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
| Native Windows game/snapshot behavior | Equivalent intended output | Not run | PENDING |
| Full 159-record XISO, both renderers | No new candidate failures | Candidate Vulkan 158 PASS / 1 inherited FAIL; OpenGL 157 PASS / 2 inherited FAIL; matching previous-main OpenGL control | PASS for incremental correctness; suite overall FAILED |
| Paired fixed-work performance | No >2% adverse regression | Not run | PENDING |

The full [TAP output](ptimer-unit.tap) has SHA-256 `48d226dcab73ee6b639506238dc0d76ab1162210d35309c9d47818d4d3f5a904`. It includes the archived #59 semantic/clock-phase controls plus new idempotent-scheduling cases. The fixture compiles the production PTIMER, PRAMDAC, and scheduling-core source with deterministic clock/timer/IRQ stubs; it does **not** exercise QEMU's real timer-list locks, Windows scheduling, PCI IRQ fan-out, or actual VMState serialization.

| Performance metric | Raw + | Fixed baseline | Previous main | Candidate | Improvement vs baseline | Improvement vs previous main |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| PGR2 snapshot p99 | `+bad` | retained separately | pending | pending | pending | pending |
| PGR2 full-start p99 | `+bad` | retained separately | pending | pending | pending | pending |
| Morrowind snapshot p99 | `+bad` | retained separately | pending | pending | pending | pending |
| Full XISO timing | `+bad` | N/A | N/A | Excluded | N/A | N/A |

No Improvement % is assigned until matched performance results exist. The prior #59 performance hold and its run-order uncertainty remain historical evidence; this source and binary require their own qualification. The next run must record timer modifications, callbacks, IRQ recomputations/transitions, and wait attribution as well as frame tails. Keep diagnostic counters out of normal timing builds.

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
