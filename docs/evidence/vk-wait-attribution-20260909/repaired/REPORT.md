# Repaired deferred logger: shutdown passes, window alignment unavailable

The exact PR57 repair produced complete deferred output on normal shutdown:
one schema, 650 ordered frames, and one terminal record with zero drops,
overflow, incomplete status or I/O errors. The one Vulkan workload completed
with the expected scene, unchanged seed and normal process/private-disk cleanup.
This verifies the shutdown repair on that cell. OpenGL remains unrun.

The collection wrapper still failed. It looked for stderr at the cell root,
although the pinned controller records logs in `control.json.launch_dir`.
Offline recovery used the actual launch directory and verified the raw output.
Before/after QPC/UTC anchors had not yet been saved when the exception occurred,
so **the telemetry cannot be aligned to the runner's 20-second UTC window**.
Keep the wrapper failure and alignment gap distinct from valid raw telemetry.
No renderer/baseline comparison or performance improvement is accepted.

Candidate `f16292b472e6bf5aa9d4448cbbf352bc13131b06`, tree
`f5cac543ac34e50f4b48f6f4b9799dfbd3bd5e8f`, was built once with the pinned
O2/LTO toolchain, with zero warnings/errors. Binary SHA-256 is
`321bbb4a60ff0e05e3d11535a6be60c7d717f38d38484d5954a62d36f29a0e5a`.
Base main `bd1fecb9` and its existing binary/results were unchanged. The earlier
schema-only failure remains in the parent directory. No Vulkan replay, baseline
rebuild/rerun, new WPR capture or suite/catalog change occurred.

[Raw numeric frames](vulkan-perf.jsonl) are preserved byte-for-byte.
[Runner observations](vulkan-run.json) retain diagnostic cadence/tails without
turning them into rendered FPS or an accepted comparison. [Host checks](host-state.json)
show 12.04 GB available before and 11.92 GB after, with WPR idle and no owned
workload/recorder/exporter/analysis process remaining. Saved traces and the
shared GUI server were preserved. [Manifest](manifest.json) pins source,
binary, build options, launch counts, setup failures and private artifact hashes.
Private logs, host paths/configuration, images, EEPROM and disks are excluded.

[Wrapper lifecycle issue](https://github.com/Mainkill1/xemu-perf-tests/issues/8)
tracks durable anchors, controller-directed artifact paths, null-safe process
queries and failure-resistant evidence/cleanup bookkeeping. Fixing the reader
or writer does not restore the lost anchors. The still-unrun OpenGL check
requires an audited GL-only wrapper and focused synthetic controls; it must
not launch Vulkan again.

[The bounded QPC analysis](QPC-ANALYSIS.md) independently excludes the first
unknown-prefix record and summarizes the remaining 649 blocks over 27.029711
seconds. `need_buffer_space` accounts for 6.491212 seconds (70.51%) of the
9.205893 seconds of recorded waits. Source and per-record correlation strongly
point to descriptor/UBO capacity handling; which limit triggers it is still
unresolved. This is attribution evidence, not a promise that this wait can be
removed. The [reproduction script](analyze-r2.py) and [numeric summary](summary.json)
retain the setup-inclusive boundary and cannot inherit the runner's 20-second
label or be joined to the earlier main ETL.
