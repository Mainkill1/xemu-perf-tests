# PR #89: bounded immutable Vulkan vertex versions

**Product:** [Mainkill1/xemu#89](https://github.com/Mainkill1/xemu/pull/89), draft; [issue #86](https://github.com/Mainkill1/xemu/issues/86). **Exact parent:** PR #87 `974f2ae63b166f64aa2ea6a77963c77481e28969` (tree `4d49acf74c5069b0cf03a995c7867f55554ac028`, Win64 executable SHA-256 `6f5a85d3200135ab1eef6efb4ba4c20697303f9f6ec5fa5f8b0567dda5822cc0`). **Final candidate:** `07eff566b17b2abb643ca55b677dd9ac3a34792e` (tree `71253ba61aef43b598961cb0e555de9bff741b16`, Win64 executable SHA-256 `594a2bed93e3ee8b2e28430608c465a187ed5958bcaa11c97852d45caeeeafe6`). **Preliminary candidate:** `e4093f40efbd4a038af5a3b46d5b671e033bb086` (Win64 SHA-256 `16684e2e5f4436c856d3b4801ffd236d5cc7382a9e36afb85a5578b82b5741fb`). The final commit changed only opt-in diagnostic field labels and schema version; both binaries require explicit source identity in the result tables. The fixed cycle baseline is `9f618d6d8c4c446ef023955f3d4de22f661f61a4` and was not rebuilt.

The patch lets small, validated draws use a private inline vertex slice when writing the fixed vertex mirror would have to interrupt a Vulkan render pass. The fixed mirror stays marked stale until a later safe update. The versioning limit is 256 vertex indices and roughly 64 KiB of packed attributes per draw; unsupported or larger layouts keep the parent path. The exact Win64 product build and two bounds-policy unit tests passed. The preliminary candidate's ordered same-page XISO leaf passed with zero VUIDs, but its opt-in counters showed **zero version selections in that fixture**. Morrowind opt-in telemetry did exercise the new path; its 767,705 selected ranges include repeated visits to stale pages, **not an equal number of parent uploads avoided**. [Diagnostic counter summary](results/diagnostic-counters.json) and compressed raw logs retain that distinction. Diagnostic timing is excluded from performance acceptance.

Positive **Improvement %** means better. Guest display-write cadence has raw direction `+good`; intervals and XISO median microseconds have `+bad`. The Morrowind measure is an NV2A guest-progress proxy, **not displayed FPS**. The first pair was candidate then parent on the same fixed snapshot, 60 seconds per cell, with identical automated input and final-image checks. Both private HDD clones were removed.

| Morrowind order | Metric | Raw + | Exact #87 | #89 | Improvement % |
| --- | --- | --- | ---: | ---: | ---: |
| Preliminary candidate → parent | guest display writes/s | `+good` | 24.929 | 26.522 | **+6.39%** |
| Preliminary candidate → parent | guest interval p95 | `+bad` | 46.579 ms | 45.676 ms | **+1.94%** |
| Preliminary candidate → parent | guest interval p99 | `+bad` | 54.625 ms | 50.767 ms | **+7.06%** |
| Parent → final candidate | guest display writes/s | `+good` | 25.079 | 26.598 | **+6.06%** |
| Parent → final candidate | guest interval p95 | `+bad` | 46.281 ms | 47.130 ms | **-1.83%** |
| Parent → final candidate | guest interval p99 | `+bad` | 52.907 ms | 52.338 ms | **+1.08%** |

The cadence gain repeated in opposite test orders. P95 is mixed, while p99 improves in both pairs. The first pair used the runtime-equivalent preliminary executable; the second pair qualifies the exact final head. Neither pair was a Morrowind map traversal. All four final-image checks passed and each private HDD was deleted. The fixed-baseline p95/p99 medians from an older session were **47.413/52.773 ms**; this final candidate cell is descriptively **+0.60%/+0.82%** against them, not a same-session baseline pass.

The exact-final-head 160-record XISO retained all parent outcomes and comparable framebuffer hashes: Vulkan 159/160 with zero VUIDs and OpenGL 158/160. The failures are inherited `report_query.dma_range_guard` (#60) and OpenGL `texture_cubemap_fallback.unbordered_subblock_dxt1` (#82). The same two successful queued same-address texture-write leaves remain hash-ineligible for cross-run comparison. These suite statuses are **FAILED**, not passes. The runner also recorded median execution time per leaf, so correctness alone does not describe this result.

| Full XISO comparison | Raw + | Exact #87 outcomes | Final #89 outcomes | Eligible timed leaves | Median Improvement % | Faster / slower leaves |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Vulkan | `+bad` median µs | 159/160 | 159/160 | 154 | **-0.17%** | 68 / 85 |
| OpenGL | `+bad` median µs | 158/160 | 158/160 | 153 | **-0.13%** | 70 / 81 |

The preliminary executable gave +0.30% Vulkan and +0.02% OpenGL suite medians, so the two same-runtime source revisions did not show a stable suite-wide gain. The final Vulkan queued-vertex-CPU-writes leaf improved **+39.79%** (83,722 → 50,411 µs), consistent with the focused version-path oracle, while Vulkan tiny inline arrays worsened **-15.21%** (37,964 → 43,740 µs). Other large shifts also appeared in query and texture leaves outside this patch's direct path; for example, the Vulkan DMA-descriptor-rewrite leaf worsened -201.70% in the final run and -239.12% in the preliminary run. These isolated times require matched reproduction before assigning causality. The fenced S3TC streaming leaf changed from -9.58% preliminary to -1.13% final on Vulkan. The runner reported missing live markers, and candidate suite executions were not interleaved with the retained parent suite. [The 320-row final comparison](results/xiso-final-parent-comparison.csv) contains each test's outcome, comparable framebuffer hash, parent/candidate median µs, and Improvement %. [Preliminary comparison](results/xiso-preliminary-parent-comparison.csv) and [final suite receipt](results/xiso-final-receipt.json) are retained separately.

The final-head focused `CrossTitleHotpath` XISO group ran with opt-in telemetry and **passed 12/12 records**, with zero Vulkan VUIDs. Its queued-vertex-writes leaf had the same `ea21c900993ea325` framebuffer hash as the exact parent, while the process recorded **81,861 versioned draws**. This ties a deterministic output oracle to actual version-path execution. An earlier attempt selected the leaf display name rather than its executable parent and produced no benchmark records; it is an excluded runner-selection failure, not an emulator failure. [Focused receipt and normalized rows](results/cross-title-diagnostic-receipt.json) and [compressed telemetry](results/cross-title-vkperf-final.ndjson.gz) retain both mechanism and output evidence.

The matched PGR2 full-start pair booted from the same clean HDD seed, entered the race scene, and recorded a 120-second window after a 30-second warmup. It was not a played lap. Both stayed at the game's 30-guest-frame/s cap, limiting sensitivity to throughput improvements.

| PGR2 full-start metric | Raw + | Exact #87 | Final #89 | Improvement % |
| --- | --- | ---: | ---: | ---: |
| Guest frames in window | N/A | 3,603 | 3,603 | N/A |
| Mean guest interval | `+bad` | 33.333 ms | 33.333 ms | +0.00% |
| Guest interval p95 | `+bad` | 33.604 ms | 33.663 ms | **-0.18%** |
| Guest interval p99 | `+bad` | 33.907 ms | 33.864 ms | +0.13% |
| Guest interval maximum | `+bad` | 40.958 ms | 34.443 ms | +15.91% |

The maximum is a single interval and may reflect run order or host state; do not promote it to a repeatable 15.9% improvement. The fixed-baseline PGR2 full-start p95/p99 medians from an earlier session were **33.482/34.253 ms**. This candidate is descriptively **-0.54%/+1.14%** against those retained medians, not a paired baseline result. [Candidate](results/pgr2-full-final-candidate.json) and [parent](results/pgr2-full-parent.json) frame summaries retain the raw intervals and counts.

The exact-head PGR2 Vulkan snapshot pair used the same saved race scene and 60-second measurement window after a 3-second warmup, with the final candidate first. This scene is less constrained by the full-start 30-frame cap. Both runner cells completed with functional and measurement status `complete`, and their private HDD clones were removed.

| PGR2 snapshot metric | Raw + | Exact #87 | Final #89 | Improvement % |
| --- | --- | ---: | ---: | ---: |
| Guest frames in window | N/A | 1,771 | 1,774 | N/A |
| Mean guest interval | `+bad` | 33.867 ms | 33.839 ms | +0.08% |
| Guest interval p95 | `+bad` | 39.632 ms | 38.970 ms | **+1.67%** |
| Guest interval p99 | `+bad` | 42.951 ms | 42.348 ms | **+1.40%** |
| Guest interval maximum | `+bad` | 57.273 ms | 52.790 ms | +7.83% |

This is one ordered pair, so the maximum and tail direction are not proven repeatable. [Candidate](results/pgr2-snapshot-final-candidate.json) and [parent](results/pgr2-snapshot-parent.json) summaries retain the interval tails. The exact-head suite does not establish an overall timing benefit, while the repeated Morrowind cadence result and targeted XISO leaf support a narrower improvement. Keep #89 draft pending matched resolution of material XISO timing swings, plus the parent #87/#85 correctness gates. No merge-ready claim is made.
