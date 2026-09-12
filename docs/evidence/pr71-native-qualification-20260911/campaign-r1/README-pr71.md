# PR71 native qualification campaign

This package adapts the retained native PGR2/Morrowind and full XISO runners for the PR71 qualification. It is deployment tooling only; it does not run benchmarks during repository validation.

The comparison roles are fixed baseline `9f618d6d8c4c446ef023955f3d4de22f661f61a4`, previous main `5edff26383c6440da35bc92b9fca35f4a404b03b`, and candidate head `e6048469f7f461ea8f0c91a4efe98f8331c9b8ce`. Previous main uses the exact-tree build from source `a08c4d92916554f55f09231f525cda1f93b55129`, tree `11981a736703553349357cd89926b443901cadb9`, and executable SHA-256 `91ca72bddb6ec21441ffbbf3ef5bdddeda84ab3b7768d1f29081dca07136c4b3`. The candidate uses its exact source, tree `e298704f3704887127965a4d03ac087f0df06b0f`, and executable SHA-256 `4df007150dcd5f25436a701c47bba76afb5c43d5a3613de9bd49980f909698dc`.

Before deployment, stage the latest current-main XISO and catalog under the lab incoming root and write `identity.json` with `TestSourceCommit`, `TestSourceTree`, `ImageSha256`, `ImageBytes`, `CatalogSha256`, `CatalogId`, `RecordCount`, `LeafCount`, `GroupCount`, `RegisteredRecordCount`, `RegisteredLeafCount`, `ExpectedOpenGlNonPass`, and `ExpectedVulkanNonPass`. The package has unresolved tokens until this current-main artifact is staged, and refuses to run with them. The expected latest XISO source is perf-tests main `0bb7618aec5ea73355a03bcb176a922ea8b3ec2e`, tree `d0dfbf18f5fccafd3fc06b2401bbe1c17affdda4`, image SHA-256 `a8f07817b9f1b22ef93ea54497ddfc9f06d34147d734e4ed26a8bcb69c7e8687`, 3,670,016 bytes, and 157/152/5 records/leaves/groups.

Run from an elevated interactive Session 1 PowerShell window after setting the lab root:

```powershell
$env:XEMU_LAB_ROOT = '<test-box lab root>'
& '<deployed campaign root>\run-all-session1.ps1'
```

The campaign executes full XISO OpenGL/Vulkan, PGR2 snapshot, PGR2 120-second fresh start, and Morrowind snapshot. Candidate Vulkan runs use isolated Hybrid ubershader Off and On profiles, each with explicit shader cache cold/warm phases. OpenGL is always Hybrid Off. Fixed and previous controls are Hybrid Off. Every cell records the exact logical/source/tree/executable/config identities, renderer and auto-GPU evidence, Vulkan validation result, cache controls, run-order bracket, and cleanup receipt. The host memory/GPU admission runs once at campaign start; per-cell checks only enforce idle emulator/trace processes.

Reports are tables only. Improvement % uses the positive-good convention: higher-is-better metrics use `+good`, lower-is-better metrics use `+bad`; favorable movement is positive and adverse movement is negative. No graphs are generated.
