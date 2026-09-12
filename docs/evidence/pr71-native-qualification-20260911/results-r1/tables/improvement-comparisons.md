# PR71 Improvement comparisons (+ favorable, - adverse)

| Workload | Renderer | Candidate_cache | Candidate_hybrid | Metric | Unit | Baseline_median | Previous_main_median | Candidate_median | Improvement_vs_baseline | Improvement_vs_previous_main | Previous_main_vs_baseline | Baseline_runs | Previous_runs | Candidate_runs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| morrowind_snapshot | opengl | none | Off | FPS / cadence | fps | 34.473 | 34.632 | 34.123 | -1.016% | -1.473% | +0.464% | 1 | 1 | 1 |
| morrowind_snapshot | opengl | none | Off | Mean interval | ms | 29.009 | 28.875 | 29.306 | -1.026% | -1.495% | +0.462% | 1 | 1 | 1 |
| morrowind_snapshot | opengl | none | Off | p95 interval | ms | 36.142 | 36.078 | 36.493 | -0.971% | -1.150% | +0.177% | 1 | 1 | 1 |
| morrowind_snapshot | opengl | none | Off | p99 interval | ms | 40.706 | 40.748 | 41.401 | -1.707% | -1.603% | -0.103% | 1 | 1 | 1 |
| morrowind_snapshot | opengl | none | Off | Maximum interval | ms | 45.407 | 76.279 | 56.742 | -24.963% | +25.613% | -67.990% | 1 | 1 | 1 |
| morrowind_snapshot | opengl | none | Off | Stalls >= 75 ms | count | 0.000 | 1.000 | 0.000 | n/a | +100.000% | n/a | 1 | 1 | 1 |
| morrowind_snapshot | vulkan | cold | Off | FPS / cadence | fps | 24.279 | 24.220 | 24.025 | -1.046% | -0.806% | -0.242% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | Off | Mean interval | ms | 41.190 | 41.289 | 41.630 | -1.069% | -0.828% | -0.239% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | Off | p95 interval | ms | 47.852 | 47.590 | 48.186 | -0.699% | -1.253% | +0.548% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | Off | p99 interval | ms | 54.121 | 53.625 | 53.893 | +0.420% | -0.501% | +0.916% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | Off | Maximum interval | ms | 62.118 | 61.980 | 67.038 | -7.920% | -8.160% | +0.222% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | Off | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | warm | Off | FPS / cadence | fps | 24.279 | 24.220 | 24.075 | -0.837% | -0.597% | -0.242% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | Off | Mean interval | ms | 41.190 | 41.289 | 41.536 | -0.841% | -0.600% | -0.239% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | Off | p95 interval | ms | 47.852 | 47.590 | 47.408 | +0.927% | +0.381% | +0.548% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | Off | p99 interval | ms | 54.121 | 53.625 | 54.759 | -1.180% | -2.116% | +0.916% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | Off | Maximum interval | ms | 62.118 | 61.980 | 61.400 | +1.156% | +0.936% | +0.222% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | Off | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | cold | On | FPS / cadence | fps | 24.279 | 24.220 | 23.869 | -1.689% | -1.451% | -0.242% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | On | Mean interval | ms | 41.190 | 41.289 | 41.900 | -1.724% | -1.481% | -0.239% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | On | p95 interval | ms | 47.852 | 47.590 | 48.689 | -1.750% | -2.310% | +0.548% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | On | p99 interval | ms | 54.121 | 53.625 | 54.865 | -1.375% | -2.312% | +0.916% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | On | Maximum interval | ms | 62.118 | 61.980 | 87.154 | -40.304% | -40.616% | +0.222% | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | cold | On | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.500 | n/a | n/a | n/a | 2 | 2 | 2 |
| morrowind_snapshot | vulkan | warm | On | FPS / cadence | fps | 24.279 | 24.220 | 24.055 | -0.921% | -0.681% | -0.242% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | On | Mean interval | ms | 41.190 | 41.289 | 41.571 | -0.926% | -0.685% | -0.239% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | On | p95 interval | ms | 47.852 | 47.590 | 47.936 | -0.177% | -0.728% | +0.548% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | On | p99 interval | ms | 54.121 | 53.625 | 53.801 | +0.590% | -0.329% | +0.916% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | On | Maximum interval | ms | 62.118 | 61.980 | 61.634 | +0.779% | +0.558% | +0.222% | 2 | 2 | 1 |
| morrowind_snapshot | vulkan | warm | On | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 1 |
| pgr2_full_start | opengl | none | Off | FPS / cadence | fps | 29.996 | 30.000 | 30.000 | +0.013% | 0.000% | +0.013% | 1 | 1 | 1 |
| pgr2_full_start | opengl | none | Off | Mean interval | ms | 33.337 | 33.333 | 33.333 | +0.012% | 0.000% | +0.013% | 1 | 1 | 1 |
| pgr2_full_start | opengl | none | Off | p95 interval | ms | 33.479 | 33.686 | 33.697 | -0.651% | -0.033% | -0.618% | 1 | 1 | 1 |
| pgr2_full_start | opengl | none | Off | p99 interval | ms | 35.038 | 33.992 | 35.044 | -0.017% | -3.095% | +2.985% | 1 | 1 | 1 |
| pgr2_full_start | opengl | none | Off | Maximum interval | ms | 41.215 | 42.349 | 48.586 | -17.884% | -14.728% | -2.751% | 1 | 1 | 1 |
| pgr2_full_start | opengl | none | Off | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 1 | 1 | 1 |
| pgr2_full_start | vulkan | cold | Off | FPS / cadence | fps | 30.000 | 30.000 | 30.000 | 0.000% | 0.000% | 0.000% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | Off | Mean interval | ms | 33.333 | 33.333 | 33.333 | 0.000% | 0.000% | 0.000% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | Off | p95 interval | ms | 33.390 | 33.577 | 33.615 | -0.674% | -0.113% | -0.560% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | Off | p99 interval | ms | 34.288 | 33.920 | 33.875 | +1.205% | +0.134% | +1.072% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | Off | Maximum interval | ms | 40.660 | 34.602 | 39.959 | +1.725% | -15.480% | +14.899% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | Off | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 2 |
| pgr2_full_start | vulkan | warm | Off | FPS / cadence | fps | 30.000 | 30.000 | 30.000 | 0.000% | 0.000% | 0.000% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | Off | Mean interval | ms | 33.333 | 33.333 | 33.333 | 0.000% | 0.000% | 0.000% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | Off | p95 interval | ms | 33.390 | 33.577 | 33.551 | -0.484% | +0.076% | -0.560% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | Off | p99 interval | ms | 34.288 | 33.920 | 33.791 | +1.448% | +0.380% | +1.072% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | Off | Maximum interval | ms | 40.660 | 34.602 | 34.529 | +15.079% | +0.211% | +14.899% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | Off | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 1 |
| pgr2_full_start | vulkan | cold | On | FPS / cadence | fps | 30.000 | 30.000 | 30.000 | 0.000% | 0.000% | 0.000% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | On | Mean interval | ms | 33.333 | 33.333 | 33.333 | 0.000% | +0.001% | 0.000% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | On | p95 interval | ms | 33.390 | 33.577 | 33.594 | -0.612% | -0.052% | -0.560% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | On | p99 interval | ms | 34.288 | 33.920 | 33.873 | +1.209% | +0.139% | +1.072% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | On | Maximum interval | ms | 40.660 | 34.602 | 45.959 | -13.031% | -32.820% | +14.899% | 2 | 2 | 2 |
| pgr2_full_start | vulkan | cold | On | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 2 |
| pgr2_full_start | vulkan | warm | On | FPS / cadence | fps | 30.000 | 30.000 | 30.000 | 0.000% | 0.000% | 0.000% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | On | Mean interval | ms | 33.333 | 33.333 | 33.333 | 0.000% | 0.000% | 0.000% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | On | p95 interval | ms | 33.390 | 33.577 | 33.630 | -0.720% | -0.159% | -0.560% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | On | p99 interval | ms | 34.288 | 33.920 | 33.782 | +1.474% | +0.407% | +1.072% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | On | Maximum interval | ms | 40.660 | 34.602 | 34.636 | +14.816% | -0.098% | +14.899% | 2 | 2 | 1 |
| pgr2_full_start | vulkan | warm | On | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 1 |
| pgr2_snapshot | opengl | none | Off | FPS / cadence | fps | 28.560 | 29.483 | 29.057 | +1.740% | -1.443% | +3.230% | 1 | 1 | 1 |
| pgr2_snapshot | opengl | none | Off | Mean interval | ms | 35.016 | 33.919 | 34.372 | +1.838% | -1.335% | +3.132% | 1 | 1 | 1 |
| pgr2_snapshot | opengl | none | Off | p95 interval | ms | 42.995 | 40.402 | 41.448 | +3.598% | -2.589% | +6.031% | 1 | 1 | 1 |
| pgr2_snapshot | opengl | none | Off | p99 interval | ms | 48.076 | 43.538 | 45.813 | +4.707% | -5.225% | +9.439% | 1 | 1 | 1 |
| pgr2_snapshot | opengl | none | Off | Maximum interval | ms | 60.681 | 60.330 | 61.050 | -0.608% | -1.193% | +0.578% | 1 | 1 | 1 |
| pgr2_snapshot | opengl | none | Off | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 1 | 1 | 1 |
| pgr2_snapshot | vulkan | cold | Off | FPS / cadence | fps | 28.625 | 29.266 | 29.451 | +2.885% | +0.633% | +2.238% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | Off | Mean interval | ms | 34.985 | 34.154 | 33.949 | +2.962% | +0.603% | +2.374% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | Off | p95 interval | ms | 41.943 | 40.572 | 39.642 | +5.485% | +2.292% | +3.268% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | Off | p99 interval | ms | 47.506 | 44.384 | 44.378 | +6.583% | +0.014% | +6.571% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | Off | Maximum interval | ms | 70.105 | 63.421 | 58.995 | +15.848% | +6.979% | +9.534% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | Off | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | warm | Off | FPS / cadence | fps | 28.625 | 29.266 | 29.140 | +1.799% | -0.430% | +2.238% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | Off | Mean interval | ms | 34.985 | 34.154 | 34.302 | +1.951% | -0.433% | +2.374% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | Off | p95 interval | ms | 41.943 | 40.572 | 40.730 | +2.891% | -0.389% | +3.268% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | Off | p99 interval | ms | 47.506 | 44.384 | 44.451 | +6.430% | -0.151% | +6.571% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | Off | Maximum interval | ms | 70.105 | 63.421 | 62.279 | +11.163% | +1.801% | +9.534% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | Off | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | cold | On | FPS / cadence | fps | 28.625 | 29.266 | 28.835 | +0.735% | -1.471% | +2.238% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | On | Mean interval | ms | 34.985 | 34.154 | 34.688 | +0.848% | -1.563% | +2.374% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | On | p95 interval | ms | 41.943 | 40.572 | 41.114 | +1.975% | -1.336% | +3.268% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | On | p99 interval | ms | 47.506 | 44.384 | 47.513 | -0.016% | -7.050% | +6.571% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | On | Maximum interval | ms | 70.105 | 63.421 | 371.600 | -430.061% | -485.925% | +9.534% | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | cold | On | Stalls >= 75 ms | count | 0.000 | 0.000 | 2.500 | n/a | n/a | n/a | 2 | 2 | 2 |
| pgr2_snapshot | vulkan | warm | On | FPS / cadence | fps | 28.625 | 29.266 | 29.192 | +1.982% | -0.251% | +2.238% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | On | Mean interval | ms | 34.985 | 34.154 | 34.257 | +2.082% | -0.299% | +2.374% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | On | p95 interval | ms | 41.943 | 40.572 | 41.261 | +1.625% | -1.698% | +3.268% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | On | p99 interval | ms | 47.506 | 44.384 | 45.249 | +4.750% | -1.949% | +6.571% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | On | Maximum interval | ms | 70.105 | 63.421 | 58.213 | +16.963% | +8.212% | +9.534% | 2 | 2 | 1 |
| pgr2_snapshot | vulkan | warm | On | Stalls >= 75 ms | count | 0.000 | 0.000 | 0.000 | n/a | n/a | n/a | 2 | 2 | 1 |
