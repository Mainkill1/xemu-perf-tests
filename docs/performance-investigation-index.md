# Current performance investigations

GitHub is the publication destination for new code, results and investigation
updates. This index links the working branches and preserves held experiments.
It does not promote diagnostic branches or supersede existing release gates.

Baseline: Mainkill1/xemu main `bd1fecb93353272dda2a810991e28945de35b665`,
tree `6824a5aa4d9ca288ac96092dc9244684e995b08d`. Existing executable SHA-256
`3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b`
and stored results are reused. No baseline rebuild per experiment.

| Branch / PR | Goal and bottleneck | Status and measured scope | Next decision |
| --- | --- | --- | --- |
| [APU prerequisite #53](https://github.com/Mainkill1/xemu/pull/53) | Make the snapshot-load test path reliable | Merged; current baseline tree includes the tested load-quiescence repair; GL/VK snapshot checks passed | Preserve baseline identity; broader performance campaign remains separate |
| [research/main-cause-counters #54](https://github.com/Mainkill1/xemu/pull/54) | Attribute repeated vCPU return/lookup work | Diagnostic draft; GL/VK counters identify frequent kernel STI/shadow polling returns; no performance gain claimed | Preserve required interrupt recognition; use measured evidence for targeted candidates |
| [research/sti-shadow-entry #55](https://github.com/Mainkill1/xemu/pull/55) | Reduce one STI-entry dispatcher return | Held: one GL/VK comparison gave no clear Vulkan benefit and mixed tails; favorable GL direction was noninterleaved/inconclusive | [IRQ/NMI/debug/fault qualification #56](https://github.com/Mainkill1/xemu/issues/56) remains open; do not promote from the small timing movement |
| [research/vk-wait-attribution #57](https://github.com/Mainkill1/xemu/pull/57) | Attribute submit/fence waits and capacity drains | Diagnostic draft; f16292b4 shutdown/raw telemetry passed for one Vulkan cell; wrapper lost clock anchors. QPC-only setup-inclusive analysis finds 6.491212s capacity-labelled wait of 9.205893s tracked wait. Current3db2bbfe GL smoke passed once | New descriptor-only, UBO-only and combined counters: build passed, Vulkan observation pending, no resource policy changed |
| [research/capture-lifecycle, perf-tests #9](https://github.com/Mainkill1/xemu-perf-tests/pull/9) | Avoid losing diagnostic anchors/artifact identity and leaving helpers behind | Stacked tooling draft8baac6af; standalone PowerShell7.6.5 controls passed once, no workloads or traces | Integrate only applicable helpers into separately reviewed launchers; caller lifecycle gates remain in [issue8](https://github.com/Mainkill1/xemu-perf-tests/issues/8) |

Evidence lives in [perf-tests draft #7](https://github.com/Mainkill1/xemu-perf-tests/pull/7):

- [Main Vulkan profile and attribution](evidence/main-vulkan-profile-20260909/REPORT.md).
- [Initial failed deferred capture](evidence/vk-wait-attribution-20260909/REPORT.md).
- [Repaired capture and retained wrapper failure](evidence/vk-wait-attribution-20260909/repaired/REPORT.md).
- [Bounded QPC-only analysis and reproducible full records](evidence/vk-wait-attribution-20260909/repaired/QPC-ANALYSIS.md).
- [Current capacity diagnostic build and OpenGL smoke](evidence/vk-capacity-20260909/REPORT.md).
- [PowerShell helper controls and memory recurrence cleanup](evidence/capture-lifecycle-20260909/REPORT.md).

The current runner reports NV2A display-write cadence and interval tails, not
rendered or host-presented FPS. Missing timing alignment, nested elapsed regions,
single-run uncertainty and failed experiments stay explicit in linked reports.
No new full XISO campaign or test-image/catalog change has occurred in this
attribution phase. Full GL/VK XISO, Morrowind and fresh-start PGR2 qualification
is required for a completed optimization; it has not been claimed here.

[Release integration issue #38](https://github.com/Mainkill1/xemu/issues/38)
continues to own the broader release gates. Updating this index is not a merge
or release-qualification decision.
