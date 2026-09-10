# PR70 full qualification

**Decision: HOLD.** The exercised exact-head correctness and cache load/save checks pass, and
the cache demonstrably converts cold shader misses into warm hits. The paired
automated PGR2 FreshBoot campaign still exceeds the 2% adverse-tail gate. The
Morrowind candidate cells are valid, but the retained previous-main controls
used for context have a different measurement duration, so they do not close
that qualification gate.

## Identities

| Role | Commit / tree | Executable SHA-256 | Use |
| --- | --- | --- | --- |
| PR70 candidate | `b14bfb745870faae500a1ecb0ff49d2143ba8bd1` / `3a79dd692d9e7f1089fa0b138d07fc4269fbd704` | `d6c0762fd672932667537b7152bf4068a7c313d2980d4b545e020e852064bc9d` | All candidate cells |
| Previous main | `e18ba8d6274cf227cc9e5ae1b5684f28ed911a99` / `3826f39bafd751596436958da355ca87e5b98c87` | `13f61e7655a7b37ea51c282335b7540b48e92dc5980af0877be2e968eb571d9a` | Same-session PGR2 controls and manual B1 |
| Previous-main build source | `19944268d97ecd92f2dcd820d6e151107833795b` / `e4d305254f64b92d1c374413bda12567874d7c14` | same binary as above | Runtime-equivalent to previous main; the later difference is the performance-template document |
| Fixed baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; compiled source `c17591d59c270b352b72e648f5ed65e4b2a3e77e` / tree `6824a5aa4d9ca288ac96092dc9244684e995b08d` | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` | Existing PGR2 results reused; no rebuild or rerun |

The full XISO used test commit
`61012b4e702fbb46a02d813e71f2159a109a1c29`, tree
`f5499b106caba6edf79ab3f7445a46503708121c`, ISO SHA-256
`6b2161f1b4abab94648f3fa0ca8da893092bab1b63d7e139a2358eb0319d05ac`,
catalog `a0d41d33…`, and 157 expected records.

## Full XISO

| Cell | Records | Known nonpass records | Hash oracle | Vulkan validation | Cache result |
| --- | ---: | --- | --- | --- | --- |
| Candidate OpenGL | 157 | `report_query.dma_range_guard`; inherited OpenGL `texture_cubemap_fallback.unbordered_subblock_dxt1` | PASS | N/A | No SPIR-V file |
| Candidate Vulkan cold | 157 | `report_query.dma_range_guard` | PASS | Active; 0 unique VUIDs | 61 misses; 61 records; 1,146,671 bytes published |
| Candidate Vulkan warm | 157 | `report_query.dma_range_guard` | PASS | Active; 0 unique VUIDs | 71 hits; 0 misses; exact cache loaded and unchanged |

The previous-main comparison is the PR14 same-suite receipt at the same test
revision. It also has 157 records, the same inherited query-range failure, zero
VUIDs on Vulkan, and the expected renderer-specific cubemap result. XISO
durations are correctness context because these Release builds lack live test
markers.

## Automated PGR2 FreshBoot

Each value below is the median of two candidate cells or the mean of the two
same-session previous-main controls B3/B4. Improvement uses positive-good
semantics: higher FPS is good; lower interval values are good.

| Metric | Previous main | Candidate cold | Improvement | Candidate warm | Improvement | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| FPS | 30.000 | 29.928 | -0.24% | 29.864 | -0.45% | PASS |
| Average (ms) | 33.333 | 33.408 | -0.22% | 33.473 | -0.42% | PASS |
| p95 (ms) | 33.431 | 34.244 | **-2.43%** | 35.381 | **-5.83%** | **HOLD** |
| p99 (ms) | 34.211 | 38.122 | **-11.43%** | 39.083 | **-14.24%** | **HOLD** |
| Maximum (ms) | 36.347 | 42.576 | **-17.14%** | 43.160 | **-18.74%** | **HOLD** |
| Stalls ≥75 ms | 0 | 0 | equal | 0 | equal | PASS |

The individual cells do not show a stable cold-versus-warm ordering: cold1 was
the worse cold run while warm2 was the worse warm run. Both candidate medians
remain outside the gate. Since the adverse warm result had 341 cache hits and
zero misses, the data does not justify assigning the tail solely to shader
compilation. The next diagnostic should align the high-tail frames with
FreshBoot shader-cache load/hit handling, shader-module creation, pipeline
creation, and Windows scheduling. No WPR capture was started during this run.

The fixed-baseline FreshBoot comparison points in the same direction: cold
p95/p99 are -2.49%/-10.51%, and warm p95/p99 are -5.89%/-13.29%. Maximum was
not recorded by the retained baseline summary and is N/A for that comparison.

## Automated PGR2 snapshot

The same-session order was previous-main B1, candidate cold, candidate warm,
previous-main B2. All cells admitted active gameplay on the first input,
advanced guest/display work, and closed normally.

| Metric | Previous-main B mean | Candidate cold | Improvement | Candidate warm | Improvement | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| FPS | 28.905 | 28.889 | -0.05% | 28.904 | -0.00% | PASS |
| Average (ms) | 34.627 | 34.588 | +0.11% | 34.591 | +0.10% | PASS |
| p95 (ms) | 41.668 | 41.358 | +0.74% | 41.361 | +0.74% | PASS |
| p99 (ms) | 46.253 | 45.182 | +2.32% | 47.149 | -1.94% | PASS |
| Maximum (ms) | 68.522 | 69.208 | -1.00% | 58.829 | +14.15% | PASS |
| Stalls ≥75 ms | 0 | 0 | equal | 0 | equal | PASS |

Compared with the older fixed baseline, the warm p99 is -4.34%. The matched
same-session bracket remains within the 2% gate, so this historical difference
is retained as context rather than overriding the matched result.

Candidate OpenGL also completed both FreshBoot and snapshot routes. Against
the reused fixed baseline, every reported metric was within 2% or improved.

## Morrowind snapshot

Morrowind has no full-start cell. The three candidate-only 60-second snapshot
cells passed focus, input, image-transition, outdoor-scene/crosshair, guest
progression, normal-close, private-HDD deletion, and immutable-seed checks.

| Renderer / cache | FPS proxy | Average (ms) | p95 (ms) | p99 (ms) | Maximum (ms) | Stalls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| OpenGL | 33.619 | 29.745 | 36.461 | 41.635 | 47.183 | 0 |
| Vulkan cold | 24.353 | 41.063 | 47.940 | 54.050 | 61.224 | 0 |
| Vulkan warm | 24.168 | 41.376 | 47.762 | 53.696 | 61.169 | 0 |

Cold Vulkan published 48 records in a 1,307,654-byte cache. Warm Vulkan loaded
that exact file, served 49 hits with zero misses, and left it byte-identical.

The retained PR14 previous-main bracket uses the same executable and snapshot
route but a 20-second measurement, while the PR70 cells use 60 seconds. Its
values are included in `morrowind-historical-context.csv` only as historical
context. They are not exact matched qualification. A same-duration
previous-main bracket remains pending; no additional capture was performed
after the mismatch was identified.

Four earlier Morrowind attempts were excluded because Windows known-folder
resolution sent their caches to shared application data. The accepted route
uses a sibling `xemu.toml`, and stderr confirmed the isolated portable base.
Attempt-owned shared caches were quarantined and removed.

## Manual PGR2 full race

The user drove one 120-second active-race cell per build/cache phase. Private
start images confirm an active race in all three cells. The runner automated
menus through the final confirmation, counted down five seconds, sent the
final input, waited a fixed seven seconds, then measured without sending any
driving input.

| Metric | Previous-main B1 | Candidate cold | Improvement | Candidate warm | Improvement |
| --- | ---: | ---: | ---: | ---: | ---: |
| FPS | 29.155 | 29.463 | +1.05% | 29.600 | +1.52% |
| Average (ms) | 34.262 | 33.944 | +0.93% | 33.776 | +1.42% |
| p95 (ms) | 41.817 | 39.741 | +4.96% | 37.773 | +9.67% |
| p99 (ms) | 49.569 | 46.010 | +7.18% | 46.694 | +5.80% |
| Maximum (ms) | 182.864 | 74.022 | +59.52% | 76.365 | +58.24% |
| Stalls ≥75 ms | 1 | 0 | better | 1 | equal |

This is exploratory route-coverage evidence. Manual driving exercises changing
map and shader states, but the route, traffic, speed, and position were not
identical. There is one previous-main control, no matched fixed-baseline
120-second run, and the fixed seven-second offset is not guest-event detection.
These results do not replace the automated HOLD or prove whole-map coverage.

| Resource | Previous-main B1 | Candidate cold | Candidate warm | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Normalized host CPU | 21.92% | 22.19% | 22.01% | Cold uses 1.21% more; warm uses 0.43% more; exploratory |
| Working-set average | 1,011.86 MiB | 1,011.75 MiB | 997.96 MiB | Cold equal; warm 1.37% lower |
| Working-set peak | 1,027.65 MiB | 1,022.93 MiB | 1,026.13 MiB | Within 0.5% |
| Private average | 2,968.42 MiB | 2,972.08 MiB | 2,969.17 MiB | Within 0.2% |
| Private peak | 2,979.38 MiB | 2,980.16 MiB | 2,993.98 MiB | Within 0.5% |
| GPU utilization average | 29.98% | 33.27% | 30.95% | Partial-window context; driving differs |
| VRAM used average | 882.02 MiB | 882.02 MiB | 882.02 MiB | Partial-window context |

Cold recorded 190 hits, 221 misses and a 5,418,200-byte published cache. Warm
loaded the exact file, recorded 484 hits and zero misses, and left it
byte-identical. CPU and process-memory values are in `metrics.csv`. NVIDIA
GPU/VRAM/power sampling covers roughly 83% of each window with a missing interval around sampler shutdown. The runner force-stops the
sampler; buffering is a suspected mechanism, not a verified cause. These
results are context only.

## Lifecycle and cleanup

All accepted cells closed normally, deleted their writable HDD clone, and left
the immutable seed unchanged. No xemu, PresentMon, WPR/WPA/xperf process or
owned trace session remains. No WPR trace was started. OpenGL runs created no
SPIR-V cache. Cold publication, exact warm loading, byte-identical clean
shutdown, truncated-cache rejection, successful replacement, and multiple
shutdown cycles were covered.

Three UI-only lifecycle gates remain pending because there is no reliable
maintained automation for them: enable-after-disabled-start requiring renderer
restart, live enabled-session off/on, and live Vulkan-to-OpenGL dirty-cache
publication. The report makes no claim for those paths.

Raw logs, lab paths, screenshots, game media, and writable images are excluded
from this package. The exact manual runner source is preserved privately with
hashes in `tooling/runner-source-receipt.json`; it must be parameterized before
publication to `xemu-perf-tests`.

## Reproducibility limits

The manifest pins build receipts, symbols, source, test image, capture durations,
and runner hashes. Exact run-time host/driver inventory and the full effective
settings are not present in this portable export; they remain a metadata gate
for independently reproducing these measurements. The public manual recipe
does not yet supply the machine-specific automation as a reusable runner.
