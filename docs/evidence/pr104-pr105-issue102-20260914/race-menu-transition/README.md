# PGR2 fresh-boot race-to-menu transition

This focused check was added after the existing retail captures were found to
stop inside the race. It uses a fresh private HDD copy for every cell, the
established PGR2 fresh-start input sequence, Vulkan at 4x scale, and persistent
shader caching disabled. The runner captures the active race and the first and
late event-selection menus after quitting approximately two seconds into the
race. Raw game images remain private; `results.csv` retains their SHA-256
identities and the visual classification.

## Result

The corruption is real, persistent after five seconds, and **not introduced by
PR #105**.

| Build / role | Hybrid | Shortcut | Repetitions | Result |
| --- | --- | --- | ---: | --- |
| PR #105 `0f45e35b32` A | On | On | 2 | 2/2 persistent corruption |
| PR #105 `0f45e35b32` B | On | Off | 2 | 1 clean, 1 persistent partial corruption |
| PR #105 `0f45e35b32` C | Off | Off | 2 | 1 clean, 1 persistent corruption |
| Retained cycle baseline source `c17591d59c` | Off | Off | 1 | Persistent corruption |
| PR #104 `d89cbb3d54` | On | On | 1 | Vulkan device loss before the transition |

The second PR #105 cycle corrupted the menu in all three settings. The retained
cycle baseline produced the same multicolored vertical texture/glyph pattern
with Hybrid and the shortcut off. PR #104 could not reach the oracle because it
hit the already documented `VK_ERROR_DEVICE_LOST` in `draw.c` during fresh
start. PR #105 therefore improves survival of this workload but does not own
the menu defect.

This check does not identify the first bad guest draw or distinguish guest
output from final presentation. Issue
[`Mainkill1/xemu#106`](https://github.com/Mainkill1/xemu/issues/106) remains the
owner for that diagnosis. The result clears the defect as a PR #105 merge
regression; it does not close the issue.

## Fixed identities

| Item | Identity |
| --- | --- |
| PR #105 source | `0f45e35b32a622da781dc5c4b8e4740e15b0a268` |
| PR #105 Win64 executable SHA-256 | `a76b68fcb9cb8c09258843c1780e48a97d23f53a7bb5ac5097fd02b864c56aab` |
| PR #104 source | `d89cbb3d54eb168f0e005b8cb4e35e36f864babf` |
| PR #104 Win64 executable SHA-256 | `5f79b6d5bf20ce24d8b1e4f0ff7e18e168773ffc7f32ee8fdcaf60f23e0e1401` |
| Logical cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` |
| Compiled baseline source | `c17591d59c270b352b72e648f5ed65e4b2a3e77e` |
| Baseline Win64 executable SHA-256 | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| HDD seed SHA-256 | `8b4f7c81be6ece5db3fc98d683d86d0515db43b2447e8dff14bfd9b45078c606` |
| Transition runner SHA-256 | `d147cabb30adef1cd977f2130f12122d05f9629820ecead93c72fb1969ff9ac0` |
| GPU | NVIDIA GeForce RTX 3070 Ti Laptop GPU |
| Driver | NVIDIA 581.95 |
| Presentation | Vulkan shared external memory |

The focused test did not use Vulkan validation and did not capture a
renderer-produced guest scanout. Those remain follow-up evidence for issue
#106, not acceptance requirements for PR #105 after the same symptom was
observed on the retained baseline.

