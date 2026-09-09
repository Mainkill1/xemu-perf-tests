# Vulkan capacity discriminator: build and OpenGL smoke

Current [diagnostic PR #57](https://github.com/Mainkill1/xemu/pull/57) at
`3db2bbfecd5153bb6841599d66bb24de731e12b7`, tree
`e76e9879fedb81973b0eb0b93b99b9d8331669c7`, distinguishes descriptor-only,
uniform-only and combined capacity triggers at the existing shader branch.
The branch predicate and finish/fence ownership are unchanged. Its schema-6
counts classify that one source site, while other capacity-drain sites retain
the broader reason counters. This is diagnostic code, not an optimization.

The exact O2/LTO build passed with zero errors and two existing `blit.c` shadow
warnings. Binary SHA-256 is
`a18ae99f2e1274cefff5c1e73d9068e606445b0a171e3c498ad4d7a8d26f99b6`.
One current-head OpenGL smoke passed: expected waterfront scene/crosshair,
automated image check, normal close, unchanged seed and removed private disk.
The runner's automatic admission/finally cleanup and environment restoration
passed. No supplemental manual memory audit was required. The dispatcher
returned and exited; the shared GUI session was preserved.

| OpenGL observation | Value |
| --- | ---: |
| Requested / measured interval | 20 s / 20.0041272 s |
| Display-write events / intervals | 681 / 680 |
| Display-write interval cadence | 34.03575967089823 per second |
| Interval p95 / p99 | 36.225 ms / 41.367 ms |

These are the pinned runner's NV2A display-write proxies, not rendered FPS or
an accepted baseline/performance comparison. All Vulkan telemetry controls were
disabled for this GL run and no Vulkan telemetry file appeared. Earlier failed
synthetic launcher controls were corrected before this one game launch. A later
unused supplemental-validator parser failure did not read a result or change
the host; it was preserved without another run. The durable launcher receipt
records acceptance.

[Sanitized runner result](opengl-run.json) and [build/test manifest](manifest.json)
pin source, binary, source-independent helper identity and private artifact
hashes. Full private paths, commands, images, logs, EEPROM and disks are excluded.
The current schema-6 Vulkan observation remains pending. The earlier f16292b4
Vulkan capture has [separate evidence](../vk-wait-attribution-20260909/repaired/REPORT.md)
and does not qualify the new fields. No baseline rebuild, WPR capture or XISO
suite change occurred.

## Offline capacity validation

The [schema-6 validator](validate_capacity_schema6.py) is pinned to this exact
source/tree/binary and checks the declared mapping, fixed capacity, complete
ordered records, explicit success metadata and full timing in every bucket.
Finish calls may exceed submissions when no command buffer is active; only
submitted/timed/wait counts must be equal. All capacity categories are a subset
of the broader finish reason. The [synthetic controls](test_validate_capacity_schema6.py)
include valid calls without submissions and malformed identity/layout/count
cases. Run them with `python3 test_validate_capacity_schema6.py`.

The first two private validator versions were rejected for a too-strong
calls-equal-submits assertion and then permissive capacity/terminal metadata.
They were corrected before native interpretation. No game or trace was run to
test these parser changes. The analyzer excludes the first unknown-prefix block
and reports QPC-only counts and elapsed waits; it does not assign per-category
wait time or claim UTC-window alignment.
