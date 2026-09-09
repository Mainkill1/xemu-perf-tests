# Portable bounded WPA export recipe

This recipe reuses a saved ETL. It does not start a recorder or workload. All
paths are caller supplied. Use a fresh output directory and retain every
manifest with the resulting CSVs.

## Inputs

The Python tools require Python 3.10 or newer. Profile derivation also requires `lxml`; bounded PE function mapping uses MinGW `x86_64-w64-mingw32-objdump` (override with `--objdump`). The wrapper was checked with Windows PowerShell 5. Run the commands below from this directory or use full script paths.

- Installed `WPAExporter.exe` from the same WPT release that serialized the
  seed profile.
- A serializer-authored `.wpaProfile` containing **Samples by Thread Name**,
  **Thread Delays**, and **GPU by Process**. The validated seed for this packet
  has SHA-256
  `c556382060f6dfe0ed1278178c6b31c57d216692430098da7f034186336cddb8`.
- Saved ETL, target process name/PID, inclusive analysis endpoints in
  nanoseconds, and an accepted PFIFO TID. A TID must come from a unique thread
  name or an exact-PE/source-exclusive frame proof; thread popularity is not
  enough.
- For function-bounded leaf summaries, the exact executable and exact defined
  text map, each with its expected SHA-256.

## Derive the three-table profile

```bash
python3 derive-wpa-profile.py \
  --seed-profile "$SEED_PROFILE" \
  --output-profile "$PROFILE" \
  --manifest "$PROFILE_MANIFEST" \
  --pid "$PID" \
  --process-name "$PROCESS_NAME" \
  --pfifo-tid "$PFIFO_TID"
```

Require three graph types, the target PID/TID filters shown in the manifest,
zero external references, and key-column count zero for all three tables. For
this packet, the command reproduces the accepted 23,446-byte profile exactly:
SHA-256
`27f529417d60bc7d5ffa487306c367f49c573e077e92bc67791905e3bb6e980d`.

If the TID is not yet known, omit `--pfifo-tid` to derive the one-table sampled
CPU discovery profile and run the exporter with `ExpectedCsvCount=1`. Do not
infer PFIFO from the largest thread total. The broad discovery export may hit
the observed WPAExporter raw-row failure; an error marker or malformed final
row rejects quantitative use even when the process exits zero.

## Export the saved trace

Run this on the Windows analysis host. `StartNs` and `EndNs` are decimal
nanoseconds; the explicit unit avoids the exporter's default-unit ambiguity.

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File .\invoke-wpa-export.ps1 `
  -Exporter $ExporterPath `
  -Etl $EtlPath `
  -Profile $ProfilePath `
  -OutputDirectory $FreshOutputDirectory `
  -StartNs $StartNanoseconds `
  -EndNs $EndNanoseconds `
  -Prefix $OutputPrefix `
  -ExpectedCsvCount 3 `
  -MaximumOutputBytes 268435456
```

Accept the export only when the wrapper exits zero. Check its manifest for the
expected ETL/profile/tool hashes, range, three CSVs, empty error-marker list,
terminal CRLF for every raw CSV, and no remaining WPA/xperf process. The size
gate runs after the exporter exits; it is a validation limit, not a live disk
or memory cap. Complete final records also cannot prove that an exporter did
not silently omit a valid block, so retain the range, row counts, partition
closure, and hashes together.

## Minimize host context

Select the three exported CSV paths by their exact table names and create a
fresh compact directory:

```bash
python3 sanitize-attribution.py \
  --sampled "$SAMPLED_CSV" \
  --precise "$PRECISE_CSV" \
  --gpu "$GPU_CSV" \
  --output-dir "$COMPACT_DIR" \
  --pid "$PID" --tid "$PFIFO_TID" \
  --image-base "$RUNTIME_IMAGE_BASE" \
  --image-end "$RUNTIME_IMAGE_END"
```

The compact files retain target IDs, timestamps, sample weights, xemu RVAs,
external leaf-module basenames, readying scope/TID, and GPU A/N/E values. They
remove full stacks, absolute non-xemu addresses, thread-start fields,
outgoing-thread fields, and readier process names. Target IDs, timing and module basenames remain in the output; the removed fields are listed in the compact manifest.

## Reproduce the numbers

```bash
python3 analyze-sanitized.py \
  --sampled "$COMPACT_DIR/sampled-pfifo.csv" \
  --precise "$COMPACT_DIR/precise-pfifo.csv" \
  --gpu "$COMPACT_DIR/gpu-process.csv" \
  --output-summary "$COMPACT_DIR/summary.json" \
  --output-leaves "$COMPACT_DIR/sampled-leaf-summary.csv" \
  --pid "$PID" --tid "$PFIFO_TID" \
  --start-s "$START_SECONDS" --end-s "$END_SECONDS" \
  --pe "$EXACT_PE" --symbol-map "$EXACT_SYMBOL_MAP" \
  --expected-pe-sha256 "$EXPECTED_PE_SHA256" \
  --expected-symbol-map-sha256 "$EXPECTED_SYMBOL_MAP_SHA256"
```

Before accepting a reproduction, compare the export manifest's raw CSV hashes
to the sanitizer manifest's source hashes, then compare the sanitizer output
hashes to the analyzer input hashes. The analyzer requires exact timestamp and
duration arithmetic, applies the disclosed Ready-Time rounding clamp, closes
running + wait + ready to the selected window, and verifies GPU intervals.
Its wait/GPU intersection is temporal overlap only. It does not establish a
fence, copy, wait source, utilization, FPS, or performance change.

## Close helpers as well as trace tools

Record owned launcher/helper process identities (PID, creation time, parent
and originating command), and check them after successful exports, failures
and timeouts. A disconnected or timed-out remote client does not establish
that its server-side work stopped. Prefer bounded direct-path status queries;
avoid recursive directory scans through large trees or reparse points.

At completion, verify WPR state, owned ETW sessions, exporters, analysis
processes and helpers, then record available/committed host memory. Stop only
processes and sessions whose ownership is established. Preserve the shared GUI
server, unrelated system/vendor sessions and saved evidence. Process-exit
checks alone are insufficient if an untracked helper still retains memory.

The exporter wrapper above supports Windows PowerShell 5. Custom named-pipe
GUI dispatch requires PowerShell 7: invoke `pwsh.exe` explicitly and use
`NamedPipeConnectionInfo::new($PipeName, 5000)` for a bounded open. The
PID/app-domain constructor is a different API and must not be substituted for
a custom pipe name. Dispose the client PowerShell and runspace objects in a
`finally` block; this does not terminate the shared GUI host. See the
[official constructor definitions](https://learn.microsoft.com/en-us/dotnet/api/system.management.automation.runspaces.namedpipeconnectioninfo.-ctor?view=powershellsdk-7.4.0).
