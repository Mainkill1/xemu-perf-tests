# Snapshot capture and paired summaries

`run_snapshot_campaign.ps1` serializes an explicitly declared case list using an existing retail snapshot runner. It accepts a local JSON manifest, requires the interactive capture session, hashes pinned inputs, preserves prior build-side summaries, refuses reused result IDs, and stops on a failed capture/cleanup gate. It never starts a second case while the first is cleaning up. Its receipt is `CAPTURE_COMPLETE`, not a gameplay or performance acceptance decision.

The manifest supplies `runner`, `receipt_root`, `capture_root`, `seed_sha256`, `builds`, `inputs`, and `cases`. Each build supplies `path`, `source`, `tree`, and `sha256`; each input supplies `path` and `sha256`. Case fields and the path-free identities/order are illustrated in the PR59 evidence manifest. Resolve local paths yourself and keep private assets and path-bearing receipts outside public source history.

From the elevated interactive session, invoke:

```powershell
& $CampaignScript -ManifestPath $LocalManifest -Phase pilot
# Review every pilot's restored scene before admitting the measured phase.
& $CampaignScript -ManifestPath $LocalManifest -Phase measured
```

The installed historical capture implementation is an external dependency, identified by hashes in the manifest. It supplies its own immutable disk cloning, input delivery, tracing, measurement windows and process cleanup. This wrapper is not a replacement for that implementation. The named-pipe dispatcher used by PR59 requires PowerShell 7. Existing controller/capture failures are retained as evidence, and no valid slow sample is excluded.

`summarize_snapshot_pairs.py` consumes a JSON list of reviewed run rows. The schema is illustrated by `test_summarize_snapshot_pairs.py` and `runs.json` in completed evidence. Mark a measured row `VALID` only after its identity, capture and visual/readiness checks; keep an invalid row as `INVALID`. Pilots carry `phase: "pilot"` and are excluded explicitly. The calculator rejects incomplete pairs, invalid measured rows, duplicate roles, changed identities, missing renderers and non-finite/nonpositive metrics.

```sh
python3 utils/summarize_snapshot_pairs.py runs.json \
  --expected-pairs 5 --renderer OPENGL --renderer VULKAN \
  --output paired-results.json
python3 -m unittest discover -s utils -p 'test_summarize_snapshot_pairs.py'
```

The output reports each pair's signed improvement and the median/range of those improvements. `+good` means a larger raw value is favorable; `+bad` means smaller is favorable. All improvement percentages are positive favorable / negative unfavorable. These descriptive statistics are not a pooled percentile, a proof of equal guest work, or an automatic performance PASS. Zero-reference metrics require a separate absolute comparison and are rejected here.
