# PR74: report bounds and idle retirement

**HOLD — all three requested workloads are complete; PR74 is not ready to merge.** The focused repair passes its targeted tests, but repeated PGR2 OpenGL frame-tail observations prevent performance acceptance. [Product PR74](https://github.com/Mainkill1/xemu/pull/74) repairs [issue60](https://github.com/Mainkill1/xemu/issues/60).

## Source and build identities

| Identity | Exact reference |
| --- | --- |
| Product candidate | `e1ec62ede550b7ab7fdf92f1d866e8747703fd0e` |
| Product tree | `8b34a2a6115246a42799f7f927933e50a413751d` |
| Windows EXE SHA-256 | `8cf23d484a36d3f93989898e7f31cfaa329c231db80b410bca6032509f508fc0` |
| Matching DWARF SHA-256 | `6730eb0f3cac314df74cf8e30cdd07290a9cf3d0a1d93c39297b1c1cd8fab7f5` |
| Previous main / PR base | `e18ba8d6274cf227cc9e5ae1b5684f28ed911a99` |
| Reused previous-main binary source | `19944268d97ecd92f2dcd820d6e151107833795b`; only template documentation differs from PR base |
| Previous-main EXE SHA-256 | `13f61e7655a7b37ea51c282335b7540b48e92dc5980af0877be2e968eb571d9a` |
| Fixed baseline | `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; retained binary source `c17591d59c270b352b72e648f5ed65e4b2a3e77e` |
| Baseline EXE SHA-256 | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Test-suite source | `fe8dc57da7001f6ac33258cceb70d6ff6c2b9411` |
| Tested XISO SHA-256 | `e0f875e2fb4df2b5b753f550890b38c793214eada9fb668291e86236a1099b46` |

The optimized Windows build uses O2, full LTO, x86-64-v3, active assertions and retained debug information. [Build receipts and test boundaries](targeted-tests.md), [XISO build/toolchain manifest](guest-build-fe8.json), and [final machine-readable qualification](qualification-summary.json) pin the tested artifacts. Existing baseline/previous-main binaries were reused; neither reference branch moved.

## Completed qualification

| Check | OpenGL | Vulkan |
| --- | --- | --- |
| Full XISO: 158 records, one run per renderer | **157 PASS / 1 inherited FAIL** | **158 PASS**, validation active, zero VUIDs |
| Report bounds oracle | PASS: A0=16,384; A1 unchanged; B0=0 complete; B1 sentinel unchanged; canaries intact | Same PASS |
| Restored 4,097-draw query-pressure oracle | PASS: ZPASS 655,424; zero tile mismatches | Same PASS |
| Morrowind snapshot: 20 seconds | Complete; visibly unpaused; cadence/p95/p99 within 2% of retained previous main | Same result |
| PGR2 full start: 30-second warmup, 60-second measurement | Complete; repeated adverse maximum intervals, **HOLD** | Complete; mean/p95/p99 within 2% of references |

All **24 targeted cases pass under Wine and native Windows**: 16 production serializer, two guarded wrapper/decoder and six real Vulkan pending/finish/retirement cases. The Vulkan tests preserve real queue/finish behavior while instrumenting external Vulkan boundaries; they do not substitute for native GPU validation. Native full-suite validation is recorded separately above.

The OpenGL failure is `texture_cubemap_fallback.unbordered_subblock_dxt1`. Its unchanged test and failure fingerprint match the retained [previous-main control](../pr14-current-main-20260910/full-xiso/receipt.json): framebuffer `0a68f0aa371576a5`, failure count 10, mask 4030. It is not relabeled PASS or attributed to PR74. [All 316 per-test records](full-xiso-results.csv) and [suite summary](full-xiso-summary.json) preserve the complete outcomes. Suite durations are diagnostic only: the missing-live-marker waiver excludes them from performance acceptance.

## Retail comparisons

Positive **Improvement %** is favorable; negative is unfavorable. Raw `+bad` means lower is better: `100 × (reference − candidate) / reference`. Raw `+good` means higher is better: `100 × (candidate / reference − 1)`. A signed observation alone is not an established speedup or regression; a result worse than 2% or an adverse tail remains an acceptance concern.

| Initial candidate run | Raw + | Baseline | Previous main | Candidate | Improvement vs baseline | Improvement vs main |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Morrowind GL cadence, events/s | +good | 32.798 | 34.243 | 33.860 | +3.237% | −1.119% |
| Morrowind GL p99, ms | +bad | 42.848 | 41.051 | 41.799 | +2.448% | −1.822% |
| Morrowind Vulkan cadence, events/s | +good | 23.723 | 24.124 | 23.876 | +0.642% | −1.028% |
| Morrowind Vulkan p99, ms | +bad | 57.134 | 53.964 | 53.823 | +5.795% | +0.261% |
| PGR2 GL p99, ms | +bad | 36.059 | 34.638 | 34.902 | +3.209% | −0.762% |
| PGR2 Vulkan p99, ms | +bad | 34.497 | 34.873 | 34.426 | +0.206% | +1.280% |

Morrowind measures display-write cadence/intervals, **not displayed FPS**. Its maximum intervals were 48.636 ms (GL) and 59.841 ms (Vulkan), neither above 75 ms. Comparable historical maximum values were not recovered, so no maximum-improvement percentage is claimed. Full mean/p95/p99/cadence/maximum rows are in [retail-results.csv](retail-results.csv); historical reference scope is in [initial retail records](retail-initial-results.json). Vulkan previous-main PGR2 values use the median of two retained runs. These historical comparisons are not concurrent paired experiments.

### Decisive OpenGL tail control

The initial candidate PGR2 GL run reached **50.133 ms**, versus retained previous-main 36.950 ms. After this adverse observation, one predeclared same-session **previous-main → candidate** pair was completed without rebuilding either executable:

| Metric | Raw + | Previous main | Candidate repeat | Improvement vs main |
| --- | --- | ---: | ---: | ---: |
| Mean interval, ms | +bad | 33.333358 | 33.391427 | −0.174% |
| p95 interval, ms | +bad | 33.817 | 33.780 | +0.109% |
| p99 interval, ms | +bad | 34.861 | 34.727 | +0.384% |
| Maximum interval, ms | +bad | **43.501** | **88.478** | **−103.393%** |
| Intervals over 50 ms | +bad | 0 | 3 | N/A: zero reference |
| Intervals over 75 ms | +bad | 0 | 1 | N/A: zero reference |

Both captures were complete, with zero focus-loss/not-responding samples and zero lost ETW events/buffers. The candidate tail is adverse despite close mean/p95/p99. **This does not establish patch causality:** the pair is not balanced by run order, and host scheduling, driver and cache state remain possible influences. Do not average away the spike or classify PR74 as performance-neutral. [Matched pair, exact hashes and admission checks](opengl-tail-control.json).

PGR2 Vulkan's initial maximum was 35.301 ms, with no interval over 40 ms. No extra Vulkan pair was run. No PGR2 snapshot was requested in this immediate three-workload campaign. The restored 4,097-draw control ran inside both full suites at the default configuration; a separate surface-scale/rollover matrix is not claimed.

## Resources, evidence and remaining gate

Full-run resource comparisons and per-thread CPU/wait attribution are incomplete. Retained resource captures do not establish efficiency changes; no CPU/GPU/memory improvement is claimed. Scheduler ETLs for all four PGR2 runs are retained and closed; their sizes and hashes are in [qualification-summary.json](qualification-summary.json). Large ETLs remain outside public source history.

The next gate is attribution of the retained OpenGL tail events and controlled qualification before a merge decision. The current repair design remains focused; these measurements do not justify a speculative renderer rewrite. All owned test/trace processes are closed, temporary writable test disks are removed, and source disk seeds are unchanged. Useful diagnostics, failed attempts and matching debug artifacts are retained.

[Download the tested XISO, manifest, full-suite record archive and measured retail frame records](https://github.com/Mainkill1/xemu-perf-tests/releases/tag/suite-fe8dc57d-20260911). This is a test-suite prerelease, not a qualified product release. The frame artifact manifest is [retail-frame-artifacts.json](retail-frame-artifacts.json). No game images, EEPROMs or private configurations are included.

## Preserved attempts and historical evidence

The first full-suite admission failed before emulator launch because generated BUILD_INFO used `clean published archive` rather than the runner's canonical `clean`. A waiver attempt was aborted and excluded. Exact published source/archive identities were checked, generated metadata was corrected to `clean`, and the same unchanged EXE ran the accepted third attempt. Original/corrected metadata and failed attempts are retained; the corrected BUILD_INFO hash is in the final summary. This was not a product rebuild or a waived dirty-source run.

The hosted XISO build remained queued and supplied no artifact; the pinned fallback build supplied the verified image. Its toolchain/cache and extracted catalog are recorded in the manifest. Native unit dispatcher/receipt failures and the extra serializer execution remain disclosed in [targeted-tests.md](targeted-tests.md).

Earlier head `05c149635b839e09bbe1c457f26f55ca4ad5be8b` retains 10/10 native serializer and 12/12 native report-control passes; those records keep their original 157-record image and EXE identity. See [historical native report](native-validation.md), [records](native-results.json), [per-test CSV](focused-results.csv), [build outcome](build-outcome.md), and [admission failure](native-results-attempt1.json). They support development history and do not replace the new exact-head qualification.

The [checker repair](checker-review.md) rejects incomplete result publication, changed B1 sentinels and ID/scenario mismatches. Seven synthetic and five existing contract tests pass, and the historical native records remain unchanged and accepted. [Query-control provenance](query-control-provenance.md) preserves the recovered fixture's attribution and original expected output; 18 focused host contracts pass.

**Final disposition: keep PR74 draft.** The three requested workloads are complete and the missing targeted tests are addressed. The repeated OpenGL tail prevents readiness confirmation; main and baseline remain unchanged.
