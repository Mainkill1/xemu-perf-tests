# Retained CpuScheduler ETL attribution

## Result

The 20 retained scheduler traces do not isolate a PTIMER, notification, or OS-wake cause for the selected maximum frames. They do show that long scheduler **Ready** delay is absent on the three inspected xemu roles: each role spends only 0.0287-0.2836 ms Ready within a selected maximum-frame window. The adverse OpenGL windows instead contain a varying mix of more Running time on the dominant unnamed and `CPU 0/TCG` threads and more Waiting time on `nv2a.pfifo_thread`.

There is no single scheduler-state pattern across the five adverse OpenGL pairs. In four pairs the second window has more Running time on both the dominant unnamed and CPU 0/TCG threads, and in four it has more PFIFO Waiting. Pair 3 instead moves about 9.4-9.7 ms out of Running and about 11.8-12.1 ms into Waiting on the dominant unnamed and CPU 0/TCG threads. Pair 5 has nearly unchanged PFIFO Waiting. These are associations inside windows of different lengths; they do not establish a critical path or say that the extra state time caused the longer frame.

The Vulkan maximum result is mixed: the second maximum is longer in three pairs and shorter in two. In each of the three longer-second pairs, the second window has more dominant/CPU Running and more PFIFO Waiting; the two shorter-second pairs do not share that direction. This pass selected one maximum frame from each run. It does not attribute Vulkan p99 behavior.

No production, build, capture, gameplay, or input change was made. B is retained baseline source `c17591d59c270b352b72e648f5ed65e4b2a3e77e`; AM is runtime `8da17c3e68c525475f55f3e9d1ddda0ad9c11d5b`. PR59 head `0043629b0bc13d2b34a1bf3c1008171ad8eecb8f` adds tests only. See the [source/build manifest](manifest.json) and [review disposition](FOLLOWUP.md).

## Performance selection

This table uses the published frame logs. Maximum interval has raw direction `+bad`. This is second-position versus first-position improvement, not candidate versus baseline; positive means the second maximum is lower: `100 * (first - second) / first`.

| Renderer / pair | First build / max (ms) | Second build / max (ms) | Max Improvement % |
|---|---:|---:|---:|
| OpenGL 1 | B / 51.343 | AM / 67.316 | -31.110% |
| OpenGL 2 | AM / 52.934 | B / 62.604 | -18.268% |
| OpenGL 3 | B / 56.068 | AM / 58.637 | -4.582% |
| OpenGL 4 | AM / 55.518 | B / 60.941 | -9.768% |
| OpenGL 5 | B / 52.460 | AM / 54.664 | -4.201% |
| Vulkan 1 | AM / 65.974 | B / 72.256 | -9.522% |
| Vulkan 2 | B / 57.005 | AM / 69.401 | -21.745% |
| Vulkan 3 | AM / 70.871 | B / 69.931 | +1.326% |
| Vulkan 4 | B / 68.902 | AM / 59.970 | +12.963% |
| Vulkan 5 | AM / 61.286 | B / 72.313 | -17.993% |

OpenGL's second-position maximum is worse in all five pairs, with median maximum Improvement **-9.768%**. Its p99 is worse in three of five pairs, so the maximum pattern must not be generalized to the distribution. Vulkan's second-position maximum is worse in three of five pairs, and its p99 is worse in two of five.

## Scheduler-state context

Microsoft defines Running as executing, Ready as executable but not scheduled, and Waiting as unable to run pending an event. CPU Usage (Precise) rows describe the new thread from its prior switch-out through ready, switch-in, and next switch-out. See Microsoft's [CPU Analysis](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis) and [critical-path and wait analysis exercise](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/optimizing-performance-and-responsiveness-exercise-3).

For this analysis each precise row is partitioned as:

- Waiting: `Last Switch-Out Time` to `Ready Time`
- Ready: `Ready Time` to `Switch-In Time`
- Running: `Switch-In Time` to `Next Switch-Out Time`

Every segment is clipped to the nominal mapped frame interval. The tables below report separate state times for the named CPU and PFIFO threads. These are attribution measurements, without an improvement direction because frame lengths and completed work differ. The mapped ETL frame duration differs from the published microsecond frame interval by at most 0.001710 ms because the retained affine clock correction is applied.

The “dominant unnamed” label means the blank-named thread with the greatest sampled weight in that run. Several blank-named xemu threads exist, so this label does not identify a main or UI thread and may not represent the same role between runs.

### OpenGL selected maxima

| Run / build | Pair / position | CPU0 Running (ms) | CPU0 Ready (ms) | CPU0 Waiting (ms) | PFIFO Waiting (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| 01 / B | 1 / first | 47.846 | 0.093 | 3.403 | 19.312 |
| 02 / AM | 1 / second | 61.092 | 0.177 | 6.046 | 36.762 |
| 07 / AM | 2 / first | 50.148 | 0.078 | 2.707 | 20.390 |
| 08 / B | 2 / second | 60.622 | 0.136 | 1.845 | 27.562 |
| 09 / B | 3 / first | 51.109 | 0.112 | 4.845 | 27.432 |
| 10 / AM | 3 / second | 41.741 | 0.235 | 16.660 | 28.056 |
| 15 / AM | 4 / first | 51.973 | 0.163 | 3.382 | 22.375 |
| 16 / B | 4 / second | 58.954 | 0.056 | 1.930 | 29.930 |
| 17 / B | 5 / first | 49.155 | 0.069 | 3.235 | 20.535 |
| 18 / AM | 5 / second | 52.748 | 0.073 | 1.842 | 20.380 |

### Vulkan selected maxima

| Run / build | Pair / position | CPU0 Running (ms) | CPU0 Ready (ms) | CPU0 Waiting (ms) | PFIFO Waiting (ms) |
| --- | --- | ---: | ---: | ---: | ---: |
| 03 / AM | 1 / first | 61.396 | 0.224 | 4.353 | 12.008 |
| 04 / B | 1 / second | 69.069 | 0.113 | 3.072 | 21.702 |
| 05 / B | 2 / first | 54.056 | 0.184 | 2.763 | 7.423 |
| 06 / AM | 2 / second | 67.110 | 0.274 | 2.015 | 17.444 |
| 11 / AM | 3 / first | 67.414 | 0.153 | 3.302 | 19.823 |
| 12 / B | 3 / second | 59.277 | 0.118 | 10.534 | 19.275 |
| 13 / B | 4 / first | 63.956 | 0.070 | 4.875 | 19.530 |
| 14 / AM | 4 / second | 55.746 | 0.043 | 4.179 | 9.879 |
| 19 / AM | 5 / first | 56.558 | 0.069 | 4.658 | 9.071 |
| 20 / B | 5 / second | 69.807 | 0.209 | 2.296 | 21.503 |

The direction counts provide the compact cross-pair view. They remain scheduler context because the first and second windows have different lengths.

| Renderer / role | Second has more Running | Second has more Ready | Second has more Waiting |
|---|---:|---:|---:|
| OpenGL / dominant unnamed | 4/5 | 4/5 | 2/5 |
| OpenGL / CPU 0/TCG | 4/5 | 4/5 | 2/5 |
| OpenGL / NV2A PFIFO | 3/5 | 4/5 | 4/5 |
| Vulkan / dominant unnamed | 3/5 | 3/5 | 1/5 |
| Vulkan / CPU 0/TCG | 3/5 | 2/5 | 1/5 |
| Vulkan / NV2A PFIFO | 2/5 | 2/5 | 3/5 |

Waiting means that a thread was not runnable. It does not identify the event being awaited. The exported `Old State` and `Old Wait Reason` columns describe the old thread switched out at the new thread's switch-in, so they were excluded from attribution to the new thread. A scheduler Ready transition is not counted as a notification or wake.

The current WPA exports have no resolved PTIMER/function attribution and no explicit timer callback, timer operation, IRQ, wait-return, notification, or wake probes. Sampled CPU stacks are used only to select a neutral unnamed-thread label and provide statistical context; they are not used to infer PTIMER calls. The retained builds have separately recorded matching DWARF artifacts; this bounded WPA export does not connect a scheduler interval to a PTIMER source path.

## Time mapping and coverage

For each run the retained recorder provides steady-state start and end pairs in both Stopwatch/QPC microseconds and UTC 100 ns ticks. The retained ETL header provides its PerfCounter UTC origin. For a frame-log QPC value `q`, the map is:

```text
etl_ns = (steady_start_utc - trace_start_utc)_ns
       + round((q - steady_start_qpc_us)
               * steady_wall_span_ns / steady_qpc_span_us)
```

The saved affine start and end anchors are retained for every run. Wall-clock spans are 1.0777-1.4440 ms shorter than QPC spans over about 60 seconds. An independent rational-arithmetic check passed all 20 maximum-frame selections and mappings; integer rounding agrees within 1 ns and the largest mapped-duration adjustment from the recorded microsecond interval is 1,710 ns. This verifies frame selection and the stored calculation, not physical clock accuracy.

The QPC values were stored at whole microseconds, UTC and the ETL header at 100 ns, and the latency between adjacent Stopwatch and `UtcNow` reads was not measured. The report therefore does not claim exact sub-millisecond point alignment. A run-01 trace marker also cannot replace the saved anchor: the mapped saved boundary is 0.1402795 s, the observed WPR process creation is 0.1431954 s, and the WPR context marker is 0.2457044 s. The marker confirms command sequencing but includes process startup delay.

Each export includes the nominal frame plus 50 ms on each side. The exact nominal partitions contain 195,758 clipped segments across 646 observed run/thread pairs and 1,938 per-thread state totals. For every thread represented in the precise export, the clipped Running, Ready, and Waiting segments form a contiguous full nominal-frame partition with zero residual and zero overlap. Independent integer-nanosecond verification passed all 646 partitions. This coverage statement does not prove that no entirely unobserved thread existed. The wider context is not fully bounded for every observed thread and is not used quantitatively.

State times from different threads overlap. Cross-thread sums are CPU-thread time, not frame wall time or a critical path.

## Export provenance and reproduction

All 20 retained ETL sizes matched the published inventory before export. Previously published ETL SHA-256 identities were carried into the provenance; the original ETLs were not freshly rehashed during this export pass. Derived CSV byte counts and transfer hashes were freshly checked. All traces report zero lost events and zero lost buffers. Exports ran serially with automatic admission requiring no tracked xemu/WPT process and at least 6,144 MiB free. The 20 exports completed in 891.560 seconds with exit code 0, producing 20 Precise and 20 Sampled CSVs. Validation found 172,488 Precise rows and 12,969 Sampled rows, no malformed records, matching remote hashes and byte counts, and terminal CRLF on every CSV. The derived archive SHA-256 is `34f914c1181f900fa99d3cc77eca8ec4c62d7190a349f378a45e3523b72048cb`. The final cleanup check found no tracked xemu, PresentMon, WPR, WPA, WPAExporter, XPerf, or Tracerpt process.

The [working WPA profile](cpu-scheduler-window.wpaProfile) SHA-256 is `6c205c7b17bf476c53d846b15b052984f93115c1e14ec68602e553c9ebf6d773`; only its fixed xemu PID filter changes per run. WPAExporter version `11.7.383+9b99bb825f` has SHA-256 `2b0271d58b3bddd9bb0409671a62636a6cf7650a644c3a19d6475f6152fa7ffb`. To reproduce a run, replace both `xemu.exe (14884)` filter values in a copy of the profile with that run's `xemu_pid` from [trace-provenance.json](trace-provenance.json). The same record provides its ETL identity and export range. The command shape is:

```text
wpaexporter.exe -i <retained.etl> -symbols -symcacheonly
  -range <frame_start_ns-50000000> <frame_end_ns+50000000>
  -profile <pid-specialized-profile> -outputfolder <out>
  -outputformat CSV -prefix <run>-
```

The compact evidence is [trace-attribution-summary.json](trace-attribution-summary.json) plus [clipped-scheduler-intervals.csv.gz](clipped-scheduler-intervals.csv.gz), whose SHA-256 is `08227355a5d2c8c87bc612ef9ef6ed947ea55136315deec8541a60590f57d0b6`. It contains neutral thread labels, thread IDs, exact integer-nanosecond offsets, and all clipped state segments. Recompute every per-thread state total, partition, key-role value, and pair summary with:

```bash
python3 check-trace-attribution.py \
  trace-attribution-summary.json clipped-scheduler-intervals.csv.gz
```

The [sanitized provenance](trace-provenance.json) publishes source/build identities, QPC/UTC/ETL anchors, exporter/profile identities, clock limitations and cleanup. The [CSV manifest](trace-export-files.json) preserves all 40 derived CSV hashes. [Independent clock selection/map checks](clock-window-verification.json), [independent scheduler partitions](scheduler-partition-verification.json) and [checker negative controls](trace-checker-negative-controls.json) accompany the replay script. Full ETLs, WPA CSVs and marker probes remain retained by run/artifact name and hash; they are not public attachments. Every published file is covered by [SHA256SUMS](SHA256SUMS).
