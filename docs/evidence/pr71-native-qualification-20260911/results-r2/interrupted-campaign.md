# PR71 r2: retail campaign interrupted for live diagnosis

The operator stopped the retail matrix on September 11 after full XISO passed and all 13 PGR2 snapshot cells completed. The active fresh-start capture was terminated deliberately; the runner recorded `campaign=failed` and `retail=failed` rather than a pass. Its final cleanup passed, and no xemu or trace processes remained. The 13 completed snapshot receipts are unchanged. This is **not** a full-retail qualification.

The candidate is product head `d21072b39fd3a84b06943977f5f441116f229b2e` with Windows executable SHA-256 `e161c4cfe6b7b6af9d91fc7f28afde52efa43e6d899db24f1b0d2a2324e0d2c5`. The full-XISO report is [full-xiso.md](full-xiso.md), and the PGR2 saved-race bracket is [pgr2-snapshot-interim.md](pgr2-snapshot-interim.md). The latter shows two cold Hybrid On stalls (85.080 and 81.425 ms) and −2.166% p99 improvement against previous main. The measured fresh-start cells are partial; do not infer a full-start or Morrowind result from them.

Ten completed PGR2 full-start cells were retained before interruption. These start without `-loadvm`, perform approximately 3,600 guest frames of gameplay each, and use the same pinned release binaries as the snapshot cells. Every listed cell reports normal close and private-HDD cleanup. They are **partial controls**, not a completed paired 13-cell fresh-start matrix.

| Completed full-start cell | Guest frames | p99 interval | Maximum | Stalls ≥75 ms |
| --- | ---: | ---: | ---: | ---: |
| Baseline OpenGL | 3,600 | 35.087 ms | 44.110 ms | 0 |
| Candidate OpenGL | 3,602 | 34.100 ms | 52.297 ms | 0 |
| Previous main OpenGL | 3,599 | 33.972 ms | 41.622 ms | 0 |
| Baseline Vulkan b1 | 3,602 | 34.173 ms | 37.661 ms | 0 |
| Candidate Vulkan Off cold r1 | 3,601 | 34.094 ms | **80.819 ms** | 1 |
| Candidate Vulkan Off warm r1 | 3,601 | 33.853 ms | 34.588 ms | 0 |
| Previous main Vulkan b1 | 3,602 | 34.031 ms | 37.582 ms | 0 |
| Candidate Vulkan Off cold r2 | 3,599 | 33.758 ms | 42.676 ms | 0 |
| Candidate Vulkan On cold r1 | 3,601 | 33.966 ms | 36.514 ms | 0 |
| Candidate Vulkan On warm r1 | 3,602 | 34.037 ms | 43.861 ms | 0 |

The one 80.819 ms Off cold maximum did not recur in the second Off cold run. This partial fresh-start set does not reproduce the two On cold saved-snapshot spikes and cannot establish that toggling Hybrid caused or cured either tail.

For the targeted follow-up, `run-pgr2-vk-telemetry-diagnostic.ps1` accepts `-AllowStoppedRetailCampaign` only when the full-XISO phase passed, all 13 PGR2 snapshot receipts passed, and retail cleanup passed. The two telemetry captures are separately identified as **diagnostic-only**. This flag does not change the interrupted campaign's failed status or authorize a performance acceptance claim.
