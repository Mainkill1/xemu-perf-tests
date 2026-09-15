# PR #89 `aa260e72` Win64 release candidate

**Status:** Published as a [diagnostic prerelease](https://github.com/Mainkill1/xemu/releases/tag/candidate-pr89-aa260e72-20260913); PRs #85, #87, and #89 remain drafts. This is a candidate artifact, not a new baseline or a merge pass.

| Identity | Value |
| --- | --- |
| Product head / tree | `aa260e72c51ebca05038a7abd0455f18e8c42084` / `b2f506ab110dcf3d4eb4773e854b9e418981ea7e` |
| Win64 executable SHA-256 | `92abb1cc287d9a025b2bedb7f1146daf27f2305ff9f7f62bee85efe850390bfb` |
| Exact #87 comparison executable | `54b879eb2602c57504e97f2899ee73b91aa22debca4373465896a40b6d8a57e2` |
| Fixed cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` |
| Toolchain | Pinned Win64 GCC image `sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`, O2/full LTO/x86-64-v3, assertions, unstripped DWARF/COFF |

The release includes the executable, detached `.debug` file, function-symbol CSV, source-file hashes, unit executables, and checksums. The first successful link used a Git-free source snapshot and left `xemu_commit` blank. We rejected that artifact for release identity, supplied `XEMU_COMMIT` in the builder snapshot, relinked, and verified that the final Windows startup banner prints the exact source commit. All 11,406 tracked regular-file hashes passed before and after the build. The final focused Windows tests passed **2/2 fetch-span** and **3/3 version-policy** cases.

The only product change since the previously tested source-equivalent #89 tree is fixed-mirror read bookkeeping: an all-inline versioned draw no longer marks its vertex pages as reads of the fixed mirror. Those false read marks could turn later writes on adjacent pages into unnecessary conflicts. The separate batch-tracking flag was left unchanged because the source audit did not establish a defect there. The source reasoning is in [ROOT-CAUSE-AUDIT.md](ROOT-CAUSE-AUDIT.md); a targeted guest oracle for the false-read sequence is still a merge gate.

## Matched Morrowind snapshot

The four 60-second Vulkan cells used the same snapshot, seed, runner, and input sequence. All completed, passed final-scene validation, and removed private HDD copies. **Guest display writes/s is a guest-progression proxy, not displayed FPS.** Positive Improvement % means better.

| Order | #87 / candidate guest writes/s | Cadence Improvement | #87 / candidate p95 ms | p95 Improvement | #87 / candidate p99 ms | p99 Improvement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| #87 → candidate | 25.990 / 26.878 | **+3.42%** | 44.500 / 44.251 | +0.56% | 51.130 / 49.557 | +3.08% |
| candidate → #87 | 25.154 / 26.199 | **+4.16%** | 47.280 / 46.579 | +1.48% | 52.981 / 52.393 | +1.11% |

The exact-head fixed-scene gain survived the bookkeeping correction, though its magnitude is smaller than the prior tree's +5.16%/+4.81%. The image hashes differ because each 60-second cell completed different amounts of guest work; each scene check passed. See [the sanitized four-cell result](results/aa260-morrowind-abba.json).

## Matched PGR2 snapshot

The four Vulkan B-3 snapshot cells used the same seed/configuration, 30-second warmup, and 60-second measurement, without ETW or PresentMon. All completed with no focus loss or unresponsive samples. One final #87 cell recorded one guest-frame stall. Positive Improvement % means lower interval.

| Order | #87 / candidate mean ms | Mean Improvement | #87 / candidate p95 ms | p95 Improvement | #87 / candidate p99 ms | p99 Improvement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| #87 → candidate | 34.078 / 34.177 | −0.29% | 40.032 / 40.567 | −1.34% | 44.392 / 43.928 | +1.05% |
| candidate → #87 | 34.168 / 34.098 | +0.21% | 40.133 / 39.740 | +0.98% | 44.648 / 44.807 | −0.36% |

The earlier two-order, multi-percent p99 loss did **not** repeat on this exact binary. These pairs are near-neutral rather than a PGR2 speedup. The prior trace selected zero versions in this PGR2 scene, so the source correction is not by itself a proven explanation for the change in p99. See [the sanitized four-cell result](results/aa260-pgr2-snapshot-abba.json).

## PGR2 full fresh start

Both Vulkan cells completed the scripted start and 120-second measurement with 3,602 guest frames, no stalls, and the same 30-frame cap. The candidate versus #87 measured mean 33.333335 versus 33.333331 ms (effectively tied), p95 33.668 versus 33.608 ms (**−0.18% Improvement**), and p99 34.028 versus 33.871 ms (**−0.46% Improvement**). This is one pair and does not establish a meaningful throughput change. [Sanitized cell results](results/aa260-pgr2-full.json).

## Latest 162-record XISO

The [candidate image](https://github.com/Mainkill1/xemu-perf-tests/releases/tag/suite-57c2438-20260912) is pinned to test source `57c2438c3d46c8f99bc18004f1fd34a5d9ed82b9`, XISO SHA-256 `6a57961a7312bb8ec125181ac5e642d194835df382cbb900c81efaf9765536cd`, and catalog SHA-256 `ea881a43ec71cc37f74e5863e00f0cf4caea94e32933a5a15063e179e743ddfb`. All cells used the same runner SHA-256 `cd51e2192bf51a5e58862b4ff5f356867119a59c95351bc3a1378994e7917558`, scale 1, and pinned executable hashes. [Sanitized receipt](results/aa260-xiso-162-receipt.json).

| Renderer / source | Records | PASS | Other outcome | New eligible outcome/hash change vs #87 | Vulkan VUIDs |
| --- | ---: | ---: | --- | ---: | ---: |
| Vulkan fixed baseline | 71 written, **0 normalized** | N/A | PFIFO assertion abort | N/A | 0 before abort |
| Vulkan #87 | 162 | 161 | Inherited report-query DMA-range failure | Reference | 0 |
| Vulkan candidate `aa260` | 162 | 161 | Same report-query failure | **0** | 0 |
| OpenGL candidate `aa260` | 162 | 159 | Report-query, small BC1 cubemap, GPU-surface vertex readback | No same-image #87 OpenGL control | N/A |

The fixed baseline aborts in the **supported assertion-enabled build** at `pgraph_inline_packet_fits()` (`pgraph.c:2824`) during the latest image. The guest wrote 71 records, then exited before closing its results JSON. The runner therefore cannot normalize a complete baseline suite. This is the pre-existing oversized-PFIFO behavior described in [xemu #34](https://github.com/Mainkill1/xemu/issues/34), not an induced PR #89 regression. Do not substitute a different XISO revision for an exact baseline comparison. The #87 and candidate Vulkan cells completed the identical 162-record image; both have the same single inherited failure and zero VUIDs. OpenGL's GPU-surface readback failure is separately tracked in [xemu #91](https://github.com/Mainkill1/xemu/issues/91).

The [162-row parent/candidate comparator](compare_xiso_162.py) produced [per-test outcomes, hashes, and Improvement %](results/aa260-vulkan-pr87-to-pr89.csv) and [a compact summary](results/aa260-vulkan-pr87-to-pr89.json). Among 156 comparable timed Vulkan leaves, the **single-pass median Improvement was −0.76%** (57 faster, 98 slower, one tied). Some individual values move sharply in both directions. These non-interleaved suite timings are directional observations, not proof of a broad slowdown or speedup. The repeated Morrowind gain above is the supported performance claim; the XISO establishes matching observable behavior for the completed candidate paths. The normalized [#87](results/aa260-vulkan-pr87-normalized.json), [candidate Vulkan](results/aa260-vulkan-pr89-normalized.json), and [candidate OpenGL](results/aa260-opengl-pr89-normalized.json) records preserve every leaf metric.

The deterministic false fixed-mirror-read, version lifetime/rollover, and surface-overlap oracles remain merge gates. The runner's optional manifest/PDB ownership flag was not supplied for these captures; the builder's tracked-file audit, embedded commit, and executable hashes independently identify the tested binary. Do not merge or rebaseline from these results alone.
