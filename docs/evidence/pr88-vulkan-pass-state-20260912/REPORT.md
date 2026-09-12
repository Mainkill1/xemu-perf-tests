# PR #88: Vulkan command-state reuse across render-pass restarts

**Product:** [Mainkill1/xemu#88](https://github.com/Mainkill1/xemu/pull/88), draft. **Tracking:** [issue #86](https://github.com/Mainkill1/xemu/issues/86). **Parent:** [PR #87](https://github.com/Mainkill1/xemu/pull/87) at `974f2ae63b166f64aa2ea6a77963c77481e28969`; executable SHA-256 `6f5a85d3200135ab1eef6efb4ba4c20697303f9f6ec5fa5f8b0567dda5822cc0`. **Candidate:** `dbe0e6b318ceeaa59dd6aacf2b7114fc46f7780d`; executable SHA-256 `da04bb81ae4f12dbf605e7da4a199eea416b3e150e6791781ed2bdfa022bdbb7`. The fixed cycle baseline is `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; its earlier evidence was retained, not rebuilt.

The candidate retains graphics pipeline, viewport, scissor, and line-width command state within a Vulkan command buffer. It skips redundant commands after a render-pass restart and restores scissor after a partial clear. It does not reduce the ordered vertex copies or render-pass count. The focused command-state unit test and exact-head Windows build passed. This report measures the real workload effect separately.

Positive **Improvement %** means better. Guest cadence has raw direction `+good`; intervals have `+bad`. Morrowind's display-write cadence is a guest progress proxy, **not displayed FPS**. Each 60-second Morrowind cell used the same fixed snapshot and input sequence; both orders were tested without GPU timestamp telemetry or ETL tracing. Final-image checks passed and private HDD clones were deleted.

| Order | Metric | Raw + | Exact #87 | PR #88 | Improvement % |
| --- | --- | --- | ---: | ---: | ---: |
| Parent → candidate | Morrowind guest display writes/s | `+good` | 24.920 | 24.843 | **-0.31%** |
| Parent → candidate | Morrowind interval p95 | `+bad` | 47.116 ms | 48.011 ms | **-1.90%** |
| Parent → candidate | Morrowind interval p99 | `+bad` | 53.505 ms | 55.837 ms | **-4.36%** |
| Candidate → parent | Morrowind guest display writes/s | `+good` | 24.886 | 24.354 | **-2.14%** |
| Candidate → parent | Morrowind interval p95 | `+bad` | 47.451 ms | 48.683 ms | **-2.60%** |
| Candidate → parent | Morrowind interval p99 | `+bad` | 54.164 ms | 55.630 ms | **-2.71%** |

The first PGR2 Vulkan snapshot pair ran parent then candidate for 60 seconds each after a three-second warmup. It favored the candidate, but lacks a reversed order and does not cancel the two adverse Morrowind pairs.

| Metric | Raw + | Exact #87 | PR #88 | Improvement % |
| --- | --- | ---: | ---: | ---: |
| PGR2 snapshot mean guest interval | `+bad` | 33.965 ms | 33.704 ms | +0.77% |
| PGR2 snapshot p95 | `+bad` | 39.348 ms | 38.839 ms | +1.29% |
| PGR2 snapshot p99 | `+bad` | 43.607 ms | 41.733 ms | +4.30% |
| PGR2 snapshot maximum | `+bad` | 56.799 ms | 52.366 ms | +7.80% |

The matched PGR2 full-start pair booted from the same clean HDD seed, entered the race scene, and recorded a 120-second window after a 30-second warmup. It is not a driven lap. Both stayed near the game's 30-guest-frame/s cap, so it has limited sensitivity to throughput gains.

| Metric | Raw + | Exact #87 | PR #88 | Improvement % |
| --- | --- | ---: | ---: | ---: |
| PGR2 full-start guest frames | N/A | 3,603 | 3,601 | N/A |
| Mean guest interval | `+bad` | 33.333 ms | 33.333 ms | +0.00% |
| Guest interval p95 | `+bad` | 33.632 ms | 33.651 ms | **-0.06%** |
| Guest interval p99 | `+bad` | 33.981 ms | 33.789 ms | +0.57% |
| Guest interval maximum | `+bad` | 35.236 ms | 34.455 ms | +2.22% |

The unchanged candidate executable ran the exact 160-record XISO catalog used by the current PR #87 parent: test source `5b9670e5bbef92ea12a303ecd7a9eef88e956ba3`, image SHA-256 `3146ad9da3a8ae8e8185699083c6888f312e9ad2a4707bded2a1c265b75db7a3`, catalog SHA-256 `98224982dd86f27cf3e8b87a2b17d34aed3c2f2d2e76b8e70a0c5c72b46899e9`, runner SHA-256 `cd51e2192bf51a5e58862b4ff5f356867119a59c95351bc3a1378994e7917558`. The suite checks correctness and output here, not paired gameplay speed.

| Renderer | PR #87 parent | PR #88 | Failed IDs | Functional hash | Vulkan VUIDs |
| --- | ---: | ---: | --- | --- | ---: |
| Vulkan | 159 / 160 | **159 / 160** | `report_query.dma_range_guard` (#60) | PASSED | 0 |
| OpenGL | 158 / 160 | **158 / 160** | `report_query.dma_range_guard` (#60), `texture_cubemap_fallback.unbordered_subblock_dxt1` (#82) | PASSED | N/A |

All 160 test IDs retained the same outcome on each renderer. Each renderer had 158 matching candidate/parent framebuffer hashes. The two nonmatching hashes are the successful queued same-address texture-write tests whose final framebuffer hashes are already declared ineligible for cross-run comparison; their internal oracles passed. The overall suite statuses remain **FAILED** due to the inherited tracked cases. [The 320 per-test records](results/xiso-parent-comparison.csv), normalized candidate data, and exact runner summaries are retained here.

### XISO performance metrics

The same 160-record suite also reports guest execution timing for each leaf. Its parent and candidate executions used the same test image/catalog and production executable types, but ran in different host sessions without an interleaved order. The runner explicitly warned that live markers were unavailable, so these timings are **exploratory, not PR-grade performance evidence**. They use each leaf's median microseconds; lower is better (`+bad`), so a positive Improvement % means faster. Five group-summary rows and failed leaves have no comparable timing percentage.

| Renderer | Eligible passing leaves | Faster | Slower | Median per-leaf Improvement % |
| --- | ---: | ---: | ---: | ---: |
| Vulkan | 154 | 75 | 78 | **-0.03%** |
| OpenGL control | 153 | 68 | 83 | **-0.30%** |

| Representative leaf | Raw + | Vulkan #87 | Vulkan #88 | Improvement % | OpenGL control Improvement % |
| --- | --- | ---: | ---: | ---: | ---: |
| `cross_title_hotpath.pipeline_state_churn` | `+bad` | 66,021 µs | 50,390 µs | **+23.68%** | -2.46% |
| `cross_title_hotpath.pgr2_small_draws` | `+bad` | 109,339 µs | 100,874 µs | **+7.74%** | -0.64% |
| `long_unlocked_scene.full_system` | `+bad` | 77,780 µs | 72,280 µs | **+7.07%** | -0.73% |
| `vertex_buffer_allocation.ordered_same_page_overwrite` | `+bad` | 15,112 µs | 14,823 µs | **+1.91%** | -0.41% |
| `cross_title_hotpath.s3tc_streaming_fenced_draws` | `+bad` | 1,216,259 µs | 1,365,981 µs | **-12.31%** | -0.82% |

These results show a useful route-specific signal in pipeline churn and small draws, alongside an adverse streaming case and nearly balanced gains/losses overall. The unchanged OpenGL path also moves in both directions, including some large short-test swings, which shows why one unpaired suite execution cannot establish causation for every leaf. [The per-test comparison CSV](results/xiso-parent-comparison.csv) contains all eligible timing percentages as well as outcomes and hashes. The controlled Morrowind and PGR2 game cells above remain the performance decision evidence.

**Disposition:** the candidate preserved the tested behavior, but it did **not** establish a performance benefit. Morrowind regressed in both test orders, while full-start PGR2 was effectively unchanged at its 30-guest-frame/s cap. The favorable single PGR2 snapshot pair is narrower than those adverse/neutral results. Keep product PR #88 in draft as a measured failed experiment; do not merge it as an optimization. The ordered vertex-copy/pass-splitting mechanism remains the larger target. The retained baseline results are from a different session and are descriptive cumulative context, not a replacement for matched incremental pairs.

For cycle context only, the retained fixed-baseline Morrowind medians were p95/p99 **47.413/52.773 ms**. PR #88's two-cell medians are **48.347/55.734 ms**, or descriptively **-1.97%/-5.61%**. The retained fixed-baseline PGR2 full-start medians were **33.482/34.253 ms**; this candidate's p95/p99 are descriptively **-0.50%/+1.35%**. These baseline comparisons cross test sessions and are not paired acceptance results.
