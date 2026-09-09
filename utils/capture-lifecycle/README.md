# Capture lifecycle helpers

`capture-lifecycle.ps1` contains three PowerShell 7 primitives for a caller that
already owns the capture runner, process query, cell lifecycle, and cleanup.

`Save-CaptureClockAnchor` records raw `Stopwatch` QPC values around a UTC sample,
the QPC frequency, and caller-supplied source and binary identities. It atomically
creates a caller-supplied anchor path in an existing directory, flushes the bytes,
and refuses to replace an existing file. Use distinct immutable paths for the
before and after anchors. These fields are raw observations; this helper does not
qualify clock accuracy, UTC precision, or cross-machine timing.

`Resolve-CaptureLaunchArtifacts` is read-only. It accepts only a closed
schema-version-1 control cell with exactly one launch and a `launch_dir` that
resolves exactly to `cell/launch-1`. Its mandatory `-Renderer VULKAN` or
`-Renderer OPENGL` parameter makes telemetry applicability explicit. Both
renderers require `control.json`, `result.json`, `actions.jsonl`, and the
required launch files (`stderr.log`, `stdout.log`, `guest-flips.log`,
`measurement-start.capture.json`, `measurement-end.capture.json`, and
`measurement-end.png`) exist. Vulkan additionally requires cell-root
`vulkan-perf.jsonl`; OpenGL does not require it and returns `telemetry = $null`
with `telemetry_applicable = $false`. It never falls back to same-named files at
the cell root.

`Assert-CaptureProcessQueryIdle` normalizes a null, empty, or singleton process
query result and throws when any non-null record remains. The caller supplies the
query and owns identity matching and query failures.

The caller saves the before anchor immediately before capture work and saves the
after anchor from its `finally` path before any fallible post-capture check. The
caller also persists a completed cell before calling the resolver and guards
observation failures from its `finally` path. This module does not orchestrate
those actions or delete caller artifacts.

Run the focused synthetic controls with PowerShell 7:

```powershell
pwsh -NoProfile -File ./utils/capture-lifecycle/test-capture-lifecycle.ps1
pwsh -NoProfile -File ./utils/capture-lifecycle/test-start-retail-snapshot-guard.ps1
pwsh -NoProfile -File ./utils/capture-lifecycle/test-pgr2-fresh-start.ps1
```

The controls create and remove only their own uniquely named temporary directory.

`start-retail-snapshot.ps1` is the lifecycle-safe replacement for the existing
retail capture launcher. It preserves the Snapshot and FreshBoot arguments, but
rejects a non-idle xemu process query instead of terminating every process named
`xemu`. Its caller still owns the returned process and all later cleanup.

`run-pgr2-fresh-start.ps1` is a narrow adapter for the existing PGR2 capture
runner's `FreshBoot` mode. It validates the executable, disc, HDD seed, renderer
config, capture runner, and sibling launcher before the call, retains the
existing input/capture flow, and writes the tested source identity beside the
run-local result. It does not implement a second capture framework.
