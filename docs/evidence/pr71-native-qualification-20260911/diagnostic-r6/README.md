# PR71: active-stage shader-key check

Product PR [#71](https://github.com/Mainkill1/xemu/pull/71) moved from `03b0d11675892b10851f54b892bd912396ae5a93` to `48059eaea0d6203013bf409ecb926b092a692ee8`. The change compares stored binding fields directly and hashes/compares only the active shader stage when using the module cache. All module-cache lookup and insertion paths use the same hash rule. Module-first lookup ordering was not changed.

The Windows O2/full-LTO production-profile build completed, and the focused Vulkan runtime-key test passed **8/8** cases under Wine, including active-stage options, fragment route, stage separation, and inactive union bytes. Its executable SHA-256 is in [lookup-check.json](lookup-check.json). This is a basic correctness check, not the full XISO suite.

One diagnostic-only PGR2 Vulkan snapshot Off/On pair completed on the test host with guest progression and automated process cleanup. The earlier pair ran for 30 seconds per cell; the new pair ran for 15 seconds per cell. Both use `XEMU_VK_PERF_LOG` schema 6 and the same host, but their unequal durations and single repetitions limit performance inference. The diagnostic source commits, trees, executable hashes, frame counts, and exact values are in [lookup-check.json](lookup-check.json).

| Timed region, ms per guest frame; lower is better | Previous On, 30 s | Candidate On, 15 s |
| --- | ---: | ---: |
| Route binding-probe hit | 0.212 | 0.196 |
| Route selection total | 0.279 | 0.268 |
| Shader binding total | 4.539 | 4.540 |
| Pipeline preparation total | 9.985 | 9.977 |

The route probe costs a little less in this short sample, but **total shader-binding time did not improve**. Candidate Off/On shader-binding times were 4.414/4.540 ms per guest frame. Candidate Off/On p99 intervals were 45.365/48.449 ms; a single instrumented pair cannot qualify that tail difference. This result does not establish recovery of PR71's earlier normal-run regression or its cold >80 ms spikes. The feature remains draft/hold pending normal-run qualification; no further matrix was run for this focused change.
