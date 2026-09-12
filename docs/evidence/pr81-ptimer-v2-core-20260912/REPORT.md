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
| Paired fixed-work performance and full XISO | No >2% adverse regression | Not run | PENDING |

The full [TAP output](ptimer-unit.tap) has SHA-256 `fc6b8fb816c0214290d843ce47f91fb7b393373ce21f85eee2ad2728ce156dfd`. It includes the archived #59 semantic/clock-phase controls plus new idempotent-scheduling cases. The fixture compiles the production PTIMER, PRAMDAC, and scheduling-core source with deterministic clock/timer/IRQ stubs; it does **not** exercise QEMU's real timer-list locks, Windows scheduling, PCI IRQ fan-out, or actual VMState serialization.

| Performance metric | Raw + | Fixed baseline | Previous main | Candidate | Improvement vs baseline | Improvement vs previous main |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| PGR2 snapshot p99 | `+bad` | retained separately | pending | pending | pending | pending |
| PGR2 full-start p99 | `+bad` | retained separately | pending | pending | pending | pending |
| Morrowind snapshot p99 | `+bad` | retained separately | pending | pending | pending | pending |
| Full XISO pass/duration | `+good` / `+bad` | retained separately | pending | pending | pending | pending |

No Improvement % is assigned until matched performance results exist. The prior #59 performance hold and its run-order uncertainty remain historical evidence; this source and binary require their own qualification. The next run must record timer modifications, callbacks, IRQ recomputations/transitions, and wait attribution as well as frame tails. Keep diagnostic counters out of normal timing builds.
