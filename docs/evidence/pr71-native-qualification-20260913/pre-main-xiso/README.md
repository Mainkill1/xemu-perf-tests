# PR #71 XISO per-test comparison

This is a **pre-PR #80 diagnostic**, not merge qualification. Candidate `fa00907d` was compared with previous main `5edff263`; current main subsequently advanced to `7a14b022`. The exact integrated comparison is tracked separately under `campaign-integrated`.

Positive improvement means a shorter guest test median. Each test
has its own workload; the median across tests is descriptive, not an
overall gameplay speedup. Only matching PASS outcomes with measured
positive medians are compared. Full rows and framebuffer hashes are
in `per-test.csv`; individual improvements are in
`per-test-improvement.csv`. Isolated inherited baseline records
are in `fixed-baseline-gated-controls.csv`.

| Candidate | Reference | Comparable tests | Better | Worse | Median improvement |
| --- | --- | ---: | ---: | ---: | ---: |
| 02-candidate-opengl | baseline | 148 | 48 | 100 | -0.762% |
| 02-candidate-opengl | previous_main | 152 | 65 | 86 | -0.218% |
| 05-candidate-vulkan-off-cold | baseline | 148 | 61 | 86 | -0.416% |
| 05-candidate-vulkan-off-cold | previous_main | 153 | 75 | 77 | -0.071% |
| 06-candidate-vulkan-off-warm | baseline | 148 | 78 | 70 | +0.056% |
| 06-candidate-vulkan-off-warm | previous_main | 153 | 83 | 70 | +0.207% |
| 07-candidate-vulkan-on-cold | baseline | 148 | 68 | 79 | -0.197% |
| 07-candidate-vulkan-on-cold | previous_main | 153 | 74 | 77 | -0.042% |
| 07-candidate-vulkan-on-cold | same_candidate_hybrid_off | 153 | 73 | 79 | -0.122% |
| 08-candidate-vulkan-on-warm | baseline | 148 | 74 | 74 | -0.002% |
| 08-candidate-vulkan-on-warm | previous_main | 153 | 76 | 76 | +0.000% |
| 08-candidate-vulkan-on-warm | same_candidate_hybrid_off | 153 | 77 | 76 | +0.022% |
