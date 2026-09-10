# Morrowind retail qualification

The reusable host package in `tools/retail-campaign` treats a full game start
and a VM snapshot restore as separate qualification gates:

| Workload | Launch and admission | Measurement |
| --- | --- | --- |
| `MORROWIND-FRESH` | Clone the pinned clean seed and config, omit `-loadvm`, follow the fixed menu/load input sequence, and require an accepted image transition plus advancing display writes. | 20 seconds; cadence, average interval, p95, p99, maximum, stalls at 75 ms, and ten worst intervals. |
| `MORROWIND-SNAPSHOT` | Clone the same pinned inputs, restore the snapshot named by the runtime manifest, wait for QMP running, then preserve the established 5-second/Start/2-second/B/2-second route and image/progression checks. | The identical 20-second cadence/tail contract. |

Every cell hashes xemu, the source HDD, renderer config, and disc before launch.
The controller copies the HDD and config into the run directory and launches
only against those private copies. It identifies the owned xemu process by PID,
session, and start time. The success and failure paths close that process and
delete the private HDD. Source hashes are checked again after measurement.

`MORROWIND-FRESH` deliberately boots the disk state from the beginning. The
internal snapshot stored in that qcow2 remains available to
`MORROWIND-SNAPSHOT`, but the fresh command line does not name or restore it.
This prevents a successful snapshot result from satisfying full-start
qualification.

The checked-in manifest is a non-launchable example with neutral relative paths
and placeholder hashes. Copy it outside the tracked tree, replace every path,
hash, and snapshot name with local values, and set `example_only` to `false`.
Relative input paths resolve from the runtime manifest's directory. Run the
no-launch contract check from Linux or Windows:

```bash
python3 tools/retail-campaign/validate_morrowind_workloads.py \
  --manifest tools/retail-campaign/morrowind-workloads.json
python3 tools/retail-campaign/validate_morrowind_workloads.py \
  --manifest tools/retail-campaign/morrowind-workloads.json \
  --print-plan MORROWIND-FRESH
```

The test runner requires an external build manifest so campaign code never
builds or silently substitutes a baseline. Its schema is:

```json
{
  "schema_version": 1,
  "builds": {
    "fixed_baseline": {
      "host_executable": ".local/artifacts/fixed-baseline/xemu.exe",
      "executable_sha256": "<64 lowercase hex characters>",
      "source_commit": "<40 lowercase hex characters>",
      "source_tree": "<40 lowercase hex characters>"
    },
    "previous_main": {"host_executable": "...", "executable_sha256": "...", "source_commit": "...", "source_tree": "..."},
    "candidate": {"host_executable": "...", "executable_sha256": "...", "source_commit": "...", "source_tree": "..."}
  }
}
```

Reuse the retained fixed-baseline executable and historical statistics. Run
`BaselineControl` only when a same-session full-start baseline is required; it
uses the pinned executable and does not rebuild it.

Keep the package files together and dispatch one workload and renderer at a
time through the existing Session 1 pipe. Host helpers and all local manifests
are explicit arguments:

```powershell
.\dispatch-morrowind-campaign.ps1 `
  -Phase Primary `
  -Workload MORROWIND-FRESH `
  -Renderer VULKAN `
  -CampaignId shader-bind-morrowind-fresh-vulkan-r1 `
  -BuildManifest .\.local\builds.json `
  -WorkloadManifest .\.local\morrowind-workloads.json `
  -ResultsRoot .\.local\results `
  -RunsRoot .\.local\runs `
  -HddSafetyTool .\.local\helpers\hdd-safety.ps1 `
  -SendKeyTool .\.local\helpers\send-key.ps1 `
  -CaptureTool .\.local\helpers\capture-window.ps1
```

Primary order is previous/candidate/candidate/previous; Repeat reverses it.
No WPR or ETL is started. Before accepting `MORROWIND-FRESH`, visually inspect
the retained route captures once on the Windows host to confirm the pinned
sequence selects the intended save and reaches gameplay. That host check is a
required admission gate; the static validator does not claim a retail launch.
