# Deferred Vulkan wait-attribution diagnostic: rejected capture

**The first native capture is unusable for wait attribution.** One 20-second
Morrowind Vulkan cell ran on diagnostic [PR 57](https://github.com/Mainkill1/xemu/pull/57).
The log contains its schema but zero frame records and no required terminal
`deferred_capture` record. OpenGL was not launched after this failure, and the
Vulkan cell was not repeated. No performance result is accepted.

The scene and normal runner cleanup passed. The retained schema confirms full
finish timing and an allocated deferred capacity of 8,192 records. Stderr
contained no telemetry write/close error; this does not establish successful
finalization. There are no original frame timestamps or counters to align or
aggregate. Missing output is the failure, regardless of clean process exit.

| Check | Result |
| --- | --- |
| Exact source review / O2-LTO build | Passed before native testing |
| Vulkan launches / requested duration | 1 / 20 seconds |
| Vulkan telemetry admission | Failed: schema only; zero frames and terminal records |
| OpenGL launches | 0; stopped after Vulkan diagnostic failure |
| Final scene / private-disk and process cleanup / unchanged seed | Passed |
| Wait attribution / performance comparison | Rejected |

Candidate `0ba4dc0772f262ac8658c025cb0c0ccd0bfe7316`, tree
`3c81d4e9f6f0e8a97fd1ad66a530ba337fe90b20`, is based on main
`bd1fecb93353272dda2a810991e28945de35b665`. Executable SHA-256 is
`df26cdbd64abc2d146e5550c2cf094eff527db557c271015af2a58ac2db016c5`.
The baseline binary and stored results were reused without rebuilding or
rerunning the baseline. The XISO suite and catalog were unchanged.

The runner's display-write cadence and interval statistics are retained in
[vulkan-run.json](vulkan-run.json) for completeness; they are diagnostic
proxies, not rendered FPS or an accepted speedup comparison. The raw
[schema-only output](vulkan-schema-only.jsonl) is preserved byte-for-byte.
[manifest.json](manifest.json) records source/build/configuration identity,
launch counts, retained private-artifact hashes, and outstanding qualification.
Full startup logs, private paths, game images and disks are excluded.

Next: establish the actual runner exit and renderer finalization call chain,
repair the diagnostic at a safe deferred-output boundary, review it, then
qualify the new source. This failed source remains part of the record. The
existing [main ETL attribution](../main-vulkan-profile-20260909/REPORT.md)
remains valid within its published limits; it does not identify a fence cause.
