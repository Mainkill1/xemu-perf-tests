# PR #71 integrated-head qualification

This is the exact overlay deployed over [`campaign-r2`](../../pr71-native-qualification-20260911/campaign-r2/) after PR #80 reached `main`. The old `fa00907d` full-XISO run remains a pre-integration diagnostic; it is not the merge comparison.

| Role | Commit | Executable SHA-256 |
| --- | --- | --- |
| Fixed cycle baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4` (source `c17591d59c270b352b72e648f5ed65e4b2a3e77e`) | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Previous main, including PR #80 | `7a14b022baa1e81e6f2f4dd1ca1fda399a6916aa` | `a2c5445474daf63e6fc49e3d28698bb8fce95911e96c51d0005a8ba15793f6f1` |
| PR #71 candidate on current main | `4f0a8797e6fd831f4c53b6bfe8c68f944236a7fa` | `773c9428c4013437f755f03c1adbd7e36b46358accfaf5b50a5ef81dc2cb28ff` |

Both new binaries used the same pinned Win64 toolchain. The candidate build and focused runtime, compiler, pipeline-worker, and PR #80 texture-binding tests passed. The test host rechecked all three binary/source identities, parsed the campaign scripts, and imported the suite runner before starting GPU tests.

The maintained XISO is perf-tests commit `0044091f59ca148ab3c0bc919add10729bfe0fe3`: 159 records, 154 leaves, image SHA-256 `a91fdcc7b87e609a98075dfe9b6225edccb00d6036cfed6a4d7ea644b53d7400`. The full-suite matrix has the fixed baseline, previous main, candidate OpenGL and Vulkan Hybrid Off/On, cold/warm Vulkan shader-cache states, and two candidate Hybrid-On cells with `vk_shader_fastpath=true`. Ten isolated fixed-baseline gated controls retain the newer inherited records. A cell's campaign `passed` status means the expected non-PASS set, functional hashes, counts, identities, and Vulkan validation matched; it does not imply every leaf is PASS.

The retail script runs **PGR2 fresh/full start** and **Morrowind snapshot**, 13 bracketed cells per workload. The known-bad PGR2 snapshot remains a separate diagnostic, not this campaign's sole performance basis. Every retail cell uses an isolated profile and private HDD; timing is from an ordinary build with detailed hybrid trace output disabled. The optional shader shortcut remains Off in the retail matrix and is evaluated separately in the full XISO matrix.

For replay, stage `campaign-r2` on the Windows test host, overlay the four PowerShell scripts here, stage the pinned binaries and XISO with matching `BUILD_INFO.txt` and `identity.json`, and place the updated [`run-suite-pr71.py`](../../pr71-native-qualification-20260911/tooling/run-suite-pr71.py) beside the other suite Python modules as `run-suite-pr71-4f0a.py`. Set `XEMU_LAB_ROOT` and use the existing Session 1 GUI dispatch for the XISO and retail scripts. The source and artifact SHA-256 checks reject a mismatched deployment.

After both campaigns finish, `write-results.ps1` produces the improvement tables and merge gates. This integrated copy includes the shortcut column in the XISO table and expects four warm-cache retail proof cells across the two requested workloads. `summarize-xiso.py` exports every XISO record's guest timing and framebuffer hash, plus separate fixed-baseline gated controls.

The first dispatch stopped before launching xemu because the copied runner still pinned the older `5edff263` previous-main commit. That rejected preflight directory was retained with a `-preflight-rejected` suffix. The runner now pins `7a14b022`, and the actual XISO campaign starts from a fresh results directory.

The first PGR2 retail cell reached the race but was rejected because PresentMon exited without a CSV. A stale `XemuLab-23-pgr2_full_start-candidate-vulkan-on-cold-r2` ETW session from an earlier run was still active. After that orphan was stopped, an independent five-second PresentMon preflight exited 0 and wrote eight CSV rows; no `XemuLab` session remained. The failed retail directory is retained as `retail-presentmon-rejected`. The retail script now checks for an orphan `XemuLab` session before starting and before each PGR2 cell, so this host condition fails before consuming a full capture.

The first restart then rejected existing PGR2 portable profile names left by the failed attempt, before launching xemu. Its receipt is retained as `retail-profile-rejected`; all nine prior PGR2 profiles were moved intact to `profiles-presentmon-rejected`. The clean retail restart uses new profiles and the same pinned binaries and XISO.
