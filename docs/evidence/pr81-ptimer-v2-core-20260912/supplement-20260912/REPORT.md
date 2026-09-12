# PR #81: additional OpenGL PGR2 full start and Morrowind snapshot

The unchanged [product PR #81](https://github.com/Mainkill1/xemu/pull/81) head `98f1a7a49cb7a6ccb8feba20438dc86f9ead58d5` was tested again against its previous-main runtime tree, represented by `6bf9e98cdee50fd73e936ff2bd5b485ce14ac4dc`. The candidate executable SHA-256 is `5da6b82f13b6ddc325972eabecb4144b72d7930c46514def369f8d4da1c050bf`; the control executable SHA-256 is `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6`. This is an extra repeat of the already-published [18-cell matrix](../REPORT.md), **not** a new code revision or a replacement for its full XISO results. The fixed baseline `9f618d6d8c4c446ef023955f3d4de22f661f61a4` was not rebuilt.

## Result and decision

Positive **Improvement %** means better. Guest progression uses `+good`; frame intervals use `+bad` (lower is better). Both matched pairs used the same renderer, immutable seed, test revision, configuration, and measurement window. The PGR2 full-start pair ran previous main then candidate; the Morrowind pair ran candidate then previous main.

| OpenGL workload | Metric | Raw + | Previous main | PR #81 | Improvement % |
| --- | --- | --- | ---: | ---: | ---: |
| PGR2 full start, 120 s | Guest FPS | `+good` | 30.000 | 30.000 | +0.00% |
| PGR2 full start, 120 s | Guest interval p95 | `+bad` | 33.577 ms | 33.564 ms | +0.04% |
| PGR2 full start, 120 s | Guest interval p99 | `+bad` | 34.028 ms | 33.957 ms | +0.21% |
| PGR2 full start, 120 s | Guest interval maximum | `+bad` | 38.505 ms | 38.791 ms | -0.74% |
| Morrowind snapshot, 60 s | Guest display writes/s | `+good` | 34.597 | 33.761 | **-2.42%** |
| Morrowind snapshot, 60 s | Guest interval p95 | `+bad` | 36.098 ms | 36.491 ms | -1.09% |
| Morrowind snapshot, 60 s | Guest interval p99 | `+bad` | 40.653 ms | 41.422 ms | -1.89% |

The PGR2 result is effectively tied and both runs admitted about 3,600 guest frames with zero intervals at or above 75 ms. The additional Morrowind pair again has worse candidate cadence. Its p99 movement is just under the 2% gate, but the two earlier order-reversed Morrowind pairs were **-2.521% and -2.403%** at p99, and this third pair does not overturn that hold. The Morrowind metric is NV2A guest display-write cadence, **not displayed FPS**.

## Test identity and limits

| Item | Identity |
| --- | --- |
| PGR2 runner | `capture-pgr2-spirv-prewarm-pr70.ps1`, SHA-256 `e03c0a37c502fbb8de65c2d1188ead29cd26b5320a606dd85e767dc0c77acfc5`; fresh-boot/race-scene protocol, 30-second warmup, 120-second measurement |
| PGR2 base config | OpenGL config SHA-256 `8a64aab830882a8939f57bc981e3c1e6f970f4c0cad5eae8373c97ff2fe0946c`; surface scale 1 |
| PGR2 seed | SHA-256 `8b4f7c81be6ece5db3fc98d683d86d0515db43b2447e8dff14bfd9b45078c606` |
| Morrowind runner | SHA-256 `9994bd2d823e8557d39aef582fef8d7f37965d54caa52eaa09514e5d256307ed`; snapshot `vm-20260905015459`, fixed input, 60-second measurement |
| Morrowind seed | SHA-256 `d178ecc4154abad5fc7cb9e428f380a1c8d49d20cbed66ba552eaaa6ed7514ad`, unchanged after both cells |
| Instrumentation | No WPR/ETL, PresentMon, or Vulkan opt-in counters; guest timing sources only |

Both PGR2 results had `status=complete`, entered the race scene, and passed the runner's private-HDD cleanup gate. Both Morrowind results had `status=complete`, final-image oracle `PASSED`, and `private_hdd_deleted=true`. Full result fields for Morrowind are in [candidate](morrowind-opengl-candidate.json) and [previous main](morrowind-opengl-parent.json); compact PGR2 results are [candidate](pgr2-full-opengl-candidate.json) and [previous main](pgr2-full-opengl-parent.json), with SHA-256s of their complete raw records. The raw captures remain on the test host; copyrighted game images are not published.

These repeated measurements support keeping PR #81 draft. They **do not identify the cause** of the OpenGL Morrowind loss. Real PTIMER queue mutations, IRQ transitions, main-loop waits, per-thread CPU, and GPU attribution remain unmeasured; repeating the same head again would add less information than measuring those paths or testing a single isolated repair. The earlier [XISO and both-renderer matrix](../REPORT.md) remain the correctness and broader workload evidence for this exact head.
