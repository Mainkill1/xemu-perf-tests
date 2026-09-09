# Current-main PTIMER baseline correction

[PR #59](https://github.com/Mainkill1/xemu/pull/59) prioritizes [masked-alarm issue #40](https://github.com/Mainkill1/xemu/issues/40), with the separately tracked [deadline issue #39](https://github.com/Mainkill1/xemu/issues/39). Main remains unchanged. Other optimization tests are paused pending this baseline decision.

![Retained baseline versus candidate Morrowind smoke metrics](metrics.png)

| Evidence | Status |
| --- | --- |
| Current-main source inspection | Both defects remain in `bd1fecb9` |
| Candidate extraction | `8da17c3e`, tree `20c4d0a4`; focused timer/state/test changes |
| Independent source review | No concrete production blocker found; pre-expiry mask/unmask control added |
| Production Xbox timer suite | 24/24 PASS natively, exit 0 |
| Shared generic timer suite | 576/576 PASS natively, exit 0; shared stub regression check |
| Exact current-main negative controls | Pending; old S-based reports do not qualify this baseline |
| Native VMState and guest checks | v4 Morrowind GL/VK smoke passed; v4/v5/v4 roundtrip pending |
| Fixed-work performance and resources | Pending; no 2% gate pass claimed |

The chart compares retained main and candidate Morrowind display-write cadence and interval tails, not rendered FPS. Both candidate cells completed, but this single non-contemporaneous comparison does not establish a causal performance improvement or pass the 2% gate. Raw numeric inputs are in [metrics.json](metrics.json), identities and artifact hashes in [manifest.json](manifest.json). Renderer: [shared chart script](../../pr-metrics-20260909/render_pr_charts.py), matplotlib 3.10.6.

The existing baseline executable is reused. Matching measurements may need collection where none exist; the baseline emulator will not be rebuilt for this experiment. Main can be updated only after the known defects are fixed and applicable correctness/performance gates pass. A measured regression above 2% rejects the candidate; missing or inconclusive evidence does not approve it.

Historical [PR #48](https://github.com/Mainkill1/xemu/pull/48) controls and snapshot observations guide the test plan but are not exact-head qualification. Tests use the existing production translation-unit target, including PRAMDAC, and distinguish helper-state controls from actual VMState streams.

## Verified candidate unit results

The optimized candidate linked with all seven recorded build options matching the retained baseline. Native Windows execution passed **24/24 Xbox production-timer controls** and **576/576 generic timer controls**, exit 0, with no stderr. [Build identity/options](build.json) and [source-pinned native results](native-units/results.json) include both unit hashes. Complete TAP is published as UTF-8 with original byte hashes retained in the manifest.

The copied build directory first required its configured mount paths, then Meson test dispatch failed on a stored API mismatch before running tests. Direct execution of the linked Windows units avoided a rebuild. The first native collector lost exit status; its complete passing TAP was insufficient for acceptance. One corrected unit-only collection recorded exit 0. These setup/collection failures remain explicit and do not count as candidate test failures or performance results.

## Morrowind GL/VK smoke

Both 20-second candidate cells reached running gameplay, passed image checks, closed normally, deleted their private HDD and preserved the immutable seed. Root independently inspected the final images and verified their hashes.

| Renderer | Cadence baseline / candidate | p95 baseline / candidate | p99 baseline / candidate |
| --- | ---: | ---: | ---: |
| Vulkan | 23.723116 / 24.632135 per second | 47.990 / 47.619 ms | 57.134 / 55.640 ms |
| OpenGL | 32.798427 / 34.254405 per second | 38.098 / 37.712 ms | 42.848 / 41.896 ms |

[Numeric comparison](morrowind-comparison.json), [Vulkan record](vulkan-morrowind.json), [OpenGL record](opengl-morrowind.json). The observed cadence changes are +3.832% and +4.439%; both interval tails also moved favorably. Host CPU/GPU/RAM/VRAM were not collected in these cells. These observations retain their drift and comparability limits; the fixed-work comparison and real v4/v5/v4 roundtrip remain separate gates.
