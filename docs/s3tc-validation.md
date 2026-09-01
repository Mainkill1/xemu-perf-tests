# Historical ENG458 S3TC validation

This document preserves the detailed ENG458 texture-correctness contract. The
current release remains identified on the [landing page](../README.md).

Historical image: `xemu-perf-tests-eng458-69a646a.iso`, source `69a646a`,
SHA-256 `32eafdf212641ff7585ee5c6fd7b45d1fe92088ef3d1f8fb7a6bc88a394131b8`.
See [`eng458-xiso-release-v1.json`](../releases/eng458-xiso-release-v1.json).
Earlier ENG454 images and the stale generic XISO are archived under
`J:\xemu-lab-working-set\archive\xiso\superseded\eng454`.

`GameLoadComposite::10-S3tcSyncFactor` emits these records in order. Its mask
may select any subset independently.

| Bit | Stage key | Representation and route | Implementation exercised |
| ---: | --- | --- | --- |
| 1 | `dxt1_same_address_wait` | DXT1, changing payload, one address, per-draw wait | Serialized control |
| 2 | `dxt1_same_address_queued` | DXT1, changing payload, one address, final wait | Ordered upload/lifetime |
| 4 | `dxt1_ring` | DXT1, changing payload, 16-address ring | Address-renaming control |
| 8 | `dxt1_dirty_once` | DXT1, cache prime plus one dirty write | Page-generation/latch |
| 16 | `rgba8_same_address_wait` | RGBA8 equivalent of bit 1 | Decoded serialized control |
| 32 | `rgba8_same_address_queued` | RGBA8 equivalent of bit 2 | Ordered upload/lifetime control |
| 64 | `rgba8_ring` | RGBA8 equivalent of bit 4 | Address-renaming control |
| 128 | `rgba8_dirty_once` | RGBA8 equivalent of bit 8 | Page-generation/latch control |
| 256 | `bc2_native_eligible` | Borderless 2D DXT3/BC2 | Native BC2 upload |
| 512 | `bc2_bordered_fallback` | Bordered 2D DXT3/BC2 | Required decoded fallback |
| 1024 | `bc3_native_eligible` | Borderless 2D DXT5/BC3 | Native BC3 upload |
| 2048 | `bc3_bordered_fallback` | Bordered 2D DXT5/BC3 | Required decoded fallback |

Selector: `game_load_composite.s3tc_sync_factor.stage_mask`. The optional
`stages` object further intersects the mask by key. Expected record count is
selected bits plus one group summary; mask `4095` expects 13 records.

Every stage records `source_kat`, `work_checksum`, `result_checksum`,
`tile_center_kat`, `framebuffer_fnv1a64`, nonfatal `oracle_status`, failure
count, and failure mask.

| Contract | Expected value |
| --- | --- |
| Normal changing-payload result KAT | `1a4ff923` |
| Dirty-once result KAT | `fede69d6` |
| DXT1 source KAT | `0ea3ddc5` |
| RGBA8 source KAT | `9b909dc5` |
| BC2 native/fallback source KAT | `0330ddc5` / `896d9dc5` |
| BC3 native/fallback source KAT | `10e7ddc5` / `c0499dc5` |
| Normal/dirty tile KAT | `acc7c6b0` / `7981b305` |

Verified historical command for all 12 routes at Vulkan 1x:

```bat
python313\python.exe run-suite.py --mode perf ^
  --test-id GameLoadComposite::10-S3tcSyncFactor ^
  --guest-iso C:\xemu-lab\suite\assets\xemu-perf-tests-eng458-69a646a.iso ^
  --backend vulkan --scale 1 --warmup-iterations 0 ^
  --completion-mode per_iteration --expected-record-count 13 ^
  --vulkan-validation
```

Repeat at 4x by changing only `--scale`. The runner injects config at
`E:\xemu_perf_tests\xemu_perf_tests_config.json`, reads
`E:\xemu_perf_tests\results.txt`, and retains byte-exact `results.txt` beside
`normalized-results.json`, `guest-config.json`, `xemu.log`, and validation
evidence in the host run directory.

The internal lab runner reformats only its dedicated disposable
`C:\xemu-lab\suite\work\test.img`; its FATX history is temporary. Public-safe
automation must create a new per-run image and refuse existing/user HDDs.

Interpretation:

- Missing/extra record: truncated run or wrong mask.
- Source KAT mismatch: wrong or corrupt generated input.
- Work/result mismatch: fixed-work contract changed.
- Tile/oracle failure: stale or incorrect texture output.
- Framebuffer change: regression signal, not hardware proof.
- VUID, assertion, crash, hang, or oracle failure: correctness failure.
- `upload_expectation`: intended route only; a path/performance claim also
  needs matching host counters.
