# PR71 revised head: PGR2 snapshot bracket (interim)

All 13 PGR2 snapshot cells completed with gameplay progression and successful cleanup. The Windows candidate executable is `e161c4cfe6b7b6af9d91fc7f28afde52efa43e6d899db24f1b0d2a2324e0d2c5`. **The snapshot was authored by older xemu source**; see [provenance and recapture gate](snapshot-provenance.md). The subsequent retail campaign was intentionally stopped to investigate the shader draw path; the partial fresh-start cells remain evidence, and Morrowind has not run. These guest-frame intervals are not displayed FPS.

| Vulkan cold p99 (+bad) | Fixed baseline | Previous main | Candidate Off | Candidate On | On Improvement vs previous | On Improvement vs baseline |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Median of two runs | 45.785 ms | 44.514 ms | 44.079 ms | 45.478 ms | **-2.166%** | +0.671% |

Cold Hybrid On incurred two ≥75 ms stalls (85.080 and 81.425 ms maxima); neither previous main nor candidate Hybrid Off incurred one. The prior candidate head had one 667 ms outlier, which did not recur here. The new head still misses the 2% incremental p99 threshold in this snapshot and is not merge-ready.

| Cell | Guest frames | p99 interval | Maximum | Stalls ≥75 ms |
| --- | ---: | ---: | ---: | ---: |
| `01-pgr2_snapshot-baseline-opengl` | 1740 | 46.386 ms | 54.571 ms | 0 |
| `02-pgr2_snapshot-candidate-opengl` | 1731 | 44.412 ms | 54.151 ms | 0 |
| `03-pgr2_snapshot-previous-opengl` | 1739 | 45.040 ms | 59.567 ms | 0 |
| `04-pgr2_snapshot-baseline-vulkan-b1` | 1752 | 45.211 ms | 69.553 ms | 0 |
| `05-pgr2_snapshot-candidate-vulkan-off-cold-r1` | 1766 | 44.049 ms | 66.859 ms | 0 |
| `06-pgr2_snapshot-candidate-vulkan-off-warm-r1` | 1754 | 44.029 ms | 51.829 ms | 0 |
| `07-pgr2_snapshot-previous-vulkan-b1` | 1763 | 44.612 ms | 67.720 ms | 0 |
| `08-pgr2_snapshot-candidate-vulkan-off-cold-r2` | 1730 | 44.110 ms | 65.984 ms | 0 |
| `09-pgr2_snapshot-candidate-vulkan-on-cold-r1` | 1752 | 45.580 ms | 85.080 ms | 1 |
| `10-pgr2_snapshot-candidate-vulkan-on-warm-r1` | 1752 | 44.430 ms | 51.384 ms | 0 |
| `11-pgr2_snapshot-candidate-vulkan-on-cold-r2` | 1741 | 45.376 ms | 81.425 ms | 1 |
| `12-pgr2_snapshot-baseline-vulkan-b2` | 1759 | 46.359 ms | 69.968 ms | 0 |
| `13-pgr2_snapshot-previous-vulkan-b2` | 1763 | 44.416 ms | 53.391 ms | 0 |

These are non-instrumented normal-run results. Do not attribute the remaining stalls to shader routing alone: a separate, diagnostic-only capture on the repaired head is needed to identify their owner. The stopped retail campaign does not qualify the PR for merging.
