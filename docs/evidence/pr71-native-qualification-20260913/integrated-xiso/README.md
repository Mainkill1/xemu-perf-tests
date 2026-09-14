# PR #71 XISO per-test comparison

Exact integrated candidate `4f0a8797` is compared with current main `7a14b022` and the fixed cycle baseline. All 11 full-suite cells and 10 isolated baseline controls completed; functional hash validation passed, Vulkan reported zero VUIDs, and non-PASS records matched the inherited control set. The default-shortcut Hybrid-On warm cell has a descriptive median test improvement of **-2.173% versus current main**; shortcut-On warm was **-0.083%**. Each warm condition ran once, so these are signals for the retail gate, not proof of a repeatable whole-game regression or gain.

Positive improvement means a shorter guest test median. Each test
has its own workload; the median across tests is descriptive, not an
overall gameplay speedup. Only matching PASS outcomes with measured
positive medians are compared. Full rows and framebuffer hashes are
in `per-test.csv`; individual improvements are in
`per-test-improvement.csv`. Isolated inherited baseline records
are in `fixed-baseline-gated-controls.csv`.

| Candidate | Reference | Comparable tests | Better | Worse | Median improvement |
| --- | --- | ---: | ---: | ---: | ---: |
| 02-candidate-opengl | baseline | 148 | 44 | 104 | -1.581% |
| 02-candidate-opengl | previous_main | 152 | 83 | 68 | +0.195% |
| 05-candidate-vulkan-off-cold | baseline | 148 | 61 | 86 | -0.360% |
| 05-candidate-vulkan-off-cold | previous_main | 153 | 69 | 83 | -0.286% |
| 06-candidate-vulkan-off-warm | baseline | 148 | 76 | 71 | +0.084% |
| 06-candidate-vulkan-off-warm | previous_main | 153 | 93 | 59 | +0.227% |
| 07-candidate-vulkan-on-cold | baseline | 148 | 72 | 75 | -0.020% |
| 07-candidate-vulkan-on-cold | previous_main | 153 | 94 | 58 | +0.446% |
| 07-candidate-vulkan-on-cold | same_candidate_hybrid_off | 153 | 84 | 68 | +0.272% |
| 08-candidate-vulkan-on-warm | baseline | 148 | 40 | 107 | -2.146% |
| 08-candidate-vulkan-on-warm | previous_main | 153 | 41 | 111 | -2.173% |
| 08-candidate-vulkan-on-warm | same_candidate_hybrid_off | 153 | 35 | 117 | -1.813% |
| 10-candidate-vulkan-fast-cold | baseline | 148 | 71 | 76 | -0.053% |
| 10-candidate-vulkan-fast-cold | previous_main | 153 | 91 | 62 | +0.214% |
| 10-candidate-vulkan-fast-cold | same_candidate_hybrid_off | 153 | 89 | 62 | +0.240% |
| 10-candidate-vulkan-fast-cold | same_hybrid_fastpath_off | 153 | 68 | 84 | -0.145% |
| 11-candidate-vulkan-fast-warm | baseline | 148 | 66 | 81 | -0.137% |
| 11-candidate-vulkan-fast-warm | previous_main | 153 | 71 | 80 | -0.083% |
| 11-candidate-vulkan-fast-warm | same_candidate_hybrid_off | 153 | 49 | 103 | -0.749% |
| 11-candidate-vulkan-fast-warm | same_hybrid_fastpath_off | 153 | 106 | 46 | +1.016% |
