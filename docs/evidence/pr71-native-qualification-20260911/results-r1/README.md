# PR #71: native qualification, exact head e6048469f7

**Decision: HOLD.** The optional Vulkan ubershader passes focused native output and the maintained XISO correctness comparison, but its cold PGR2 snapshot and Morrowind snapshot performance does not meet the 2% incremental gate. No speedup or merge qualification is claimed. All figures below are measured guest-frame intervals; positive Improvement % is favorable.

| Cold Vulkan workload | Reference p99 (previous main) | Hybrid Off p99 | Hybrid On p99 | On Improvement vs previous | On maximum (two runs) | On stalls ≥75 ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PGR2 snapshot, 60 s | 44.384 ms | 44.378 ms | 47.513 ms | **-7.050%** | 667.100, 76.099 ms | 4, 1 |
| PGR2 full start, 120 s | 33.920 ms | 33.875 ms | 33.873 ms | +0.139% | 50.300, 41.617 ms | 0, 0 |
| Morrowind snapshot, 60 s | 53.625 ms | 53.893 ms | 54.865 ms | **-2.312%** | 106.983, 67.325 ms | 1, 0 |

Each cold Vulkan role was run twice, with a separate one-run warm cache functional check for each candidate setting. The Morrowind Off maximum also worsened against previous main (-8.160%); it is separately visible in the complete results and must not be attributed solely to the enabled ubershader. The 667 ms PGR2 interval is one run, not an established repeatable 667 ms effect. The completed campaign reports eight incremental and four cycle comparison gates on hold. Its runner performed one initial memory admission and checked each workload's guest progression, frame count, native result, GPU validation, source/build identity, and cleanup; the final cleanup passed.

The latest full XISO uses [test revision 0bb7618](https://github.com/Mainkill1/xemu-perf-tests/commit/0bb7618aec5ea73355a03bcb176a922ea8b3ec2e), SHA-256 `a8f07817b9f1b22ef93ea54497ddfc9f06d34147d734e4ed26a8bcb69c7e8687`, with 157 records, 152 leaves and five groups. Previous main and candidate completed all 157 records with matching functional hashes. Vulkan validation was active with zero VUIDs. `report_query.dma_range_guard` remains a shared nonpass; OpenGL also retains `texture_cubemap_fallback.unbordered_subblock_dxt1`. The fixed baseline has 152 registered records in its main run; the five gated newer records were checked separately, including inherited PFIFO assertion aborts. The [full XISO table](tables/full-xiso.md) shows every cell and inherited outcome.

Persistent shader reuse works: candidate cold/warm Vulkan XISO moves from 61 misses and 10 hits to 0 misses and 71 hits with Hybrid Off, and from 64 misses and 10 hits to 0 misses and 74 hits with Hybrid On. The warm checks do not qualify performance because they are one run each and did not replace repeated cold comparisons.

| Build role | Logical source | Source tree | Windows executable SHA-256 |
| --- | --- | --- | --- |
| Fixed cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` | `6824a5aa4d9ca288ac96092dc9244684e995b08d` | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Previous main | `5edff26383c6440da35bc92b9fca35f4a404b03b` | `11981a736703553349357cd89926b443901cadb9` | `91ca72bddb6ec21441ffbbf3ef5bdddeda84ab3b7768d1f29081dca07136c4b3` |
| PR #71 candidate | `e6048469f7f461ea8f0c91a4efe98f8331c9b8ce` | `e298704f3704887127965a4d03ac087f0df06b0f` | `4df007150dcd5f25436a701c47bba76afb5c43d5a3613de9bd49980f909698dc` |

The previous-main executable is an archived clean-source build with the exact tree of logical previous main; its build metadata records the archive source `a08c4d92916554f55f09231f525cda1f93b55129`. The runner records that provenance rather than calling it an exact logical-commit binary. Candidate and reference used Windows O2/full LTO/x86-64-v3 release configurations. The test host ran the NVIDIA auto-adapter path. Raw screenshots, gameplay media, private disk images, and per-frame logs remain on the controlled test box, not in this repository.

Reviewable evidence: [all retail cells](tables/retail-cells.md), [complete Improvement % comparisons](tables/improvement-comparisons.md), [all XISO outcomes](tables/full-xiso.md), [cache receipts](tables/cache-proof.md), and the [sanitized qualification summary](qualification-summary.json). The reusable [campaign source](../campaign-r1/README-pr71.md) pins the suite, executable hashes, measurement procedure, and cleanup rules. The next step is targeted source attribution for first-use fallback shader/pipeline creation and specialist pipeline creation before modifying the product route; any revised head requires the complete requested campaign again.
