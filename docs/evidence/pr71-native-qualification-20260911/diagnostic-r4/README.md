# PR71: live shader-path attribution on the repaired head

This isolated 60-second PGR2 Vulkan snapshot pair uses source `3d4bf755d24564c6a39c99dd05fd9cfb949b94fd`, the diagnostic instrumentation of PR71 product head `d21072b39fd3a84b06943977f5f441116f229b2e`. Windows executable SHA-256: `7e7a24c78b2c8c9265a68f1248c1ab2eaf1a1a2212834f7dba3b5269bf27754d`. Both Off/On captures completed and their cleanup passed. This run followed an **intentionally interrupted** retail campaign: full XISO and 13 PGR2 snapshot cells completed, but the full-start matrix and Morrowind did not. See [interrupted-campaign.md](../results-r2/interrupted-campaign.md).

This instrumentation alters CPU timing. The values below locate work in a diagnostic build; **they are not normal-run performance deltas**. Shader cache remained enabled in both runs.

| Timed region per guest frame (lower is better) | Hybrid Off | Hybrid On | On − Off |
| --- | ---: | ---: | ---: |
| Shader route selection | 0.180 ms | 1.307 ms | **+1.126 ms** |
| Shader binding (contains route selection) | 4.814 ms | 5.764 ms | +0.949 ms |
| Pipeline preparation (contains binding) | 10.211 ms | 11.266 ms | +1.055 ms |
| Entire Vulkan wait sample | 11.033 ms | 11.436 ms | +0.402 ms |

Route selection was invoked about 3,078 times per guest frame in **both** cells. Hybrid On packed fallback controls just 0.005 times per guest frame, spent less than 0.001 ms per guest frame there, and recorded **zero fallback module creations and zero fallback pipeline misses**. The earlier control-packing fix is working, but the route-selection lookup on already available specialized shaders still costs roughly 1.1 ms per frame. Nested region times must not be added.

The slowest diagnostic On frame was 56.930 ms. It contained 12.582 ms in `vkCreateGraphicsPipelines()` for a **specialized** pipeline, plus 2.390 ms of route selection; no fallback pipeline was created. The 81–85 ms cold On spikes from the uninstrumented bracket did **not** recur in this diagnostic pair, so their owner remains unproven. The Off control's slowest frame was 52.381 ms. Do not use these unequal single captures to assert a p99 or FPS gain.

Source tracing points to `select_fragment_route_impl()`: on every dirty shader-state draw it hashes and probes the full specialized binding key. The module-first suggestion from this initial trace was **superseded** by the finer [r5 lookup diagnosis](../diagnostic-r5/README.md): most binding probes were hits for an unchanged, already-bound specialized state. The targeted repair now bypasses route selection in that case. Preserve fallback and retry behavior and require normal-run correctness/performance gates before merging.

Selected per-frame facts, aggregate counters, and exact identities: [route-attribution.json](route-attribution.json). Raw diagnostic frame data is retained on the test host in `C:\xemu-lab\captures\pr71-live-debug-r4`; no diagnostic binaries are release candidates.
