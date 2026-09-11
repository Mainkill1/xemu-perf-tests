# Issue 60 focused native validation

Status: **bounded candidate validation passed**. The exact PR 74 candidate passed the focused writer unit on the builder and on Windows, then passed six report-query leaves on both OpenGL and Vulkan. This result qualifies only the tested report behavior. It does not qualify performance, the full catalog, retail software, or hardware-accurate invalid-command policy.

## Pinned identities

| Item | Identity |
| --- | --- |
| Candidate source | `05c149635b839e09bbe1c457f26f55ca4ad5be8b` |
| Candidate tree | `f1479bd7e58371f8b03233b73bf239b93dd5a024` |
| Draft product PR | `Mainkill1/xemu#74` |
| Candidate `xemu.exe` | SHA-256 `9a08f60052d50ffc714baac85bbe6d8d4a25aeea4a623f0394b21d0c2342fb09` |
| Writer unit | `test-xbox-pgraph-reports.exe`, SHA-256 `cb460eb5d568c0d4757c7fdd0aba0a52df24637ef33c1ae81bcd413b536ea4e1` |
| Verified build receipt | SHA-256 `46fad80dbb336d75360e25b481a59223bc94551381ac94ebd8c7c97c8ac89567` |
| Build information | SHA-256 `49aa5fe6b052558329f351f4d79aa41033c44f35d35eae601d9c3b78125e419e` |
| Guest test source/tree | `61012b4e702fbb46a02d813e71f2159a109a1c29` / `f5499b106caba6edf79ab3f7445a46503708121c` |
| XISO | 3,670,016 bytes, SHA-256 `6b2161f1b4abab94648f3fa0ca8da893092bab1b63d7e139a2358eb0319d05ac` |
| Catalog | 157 records, SHA-256 `8298d8baa59144caa4fd8715c4709b86e40e47fb5f830539b853fefa2a9f1a29` |
| Installed runner | SHA-256 `169ec960a057dc66dfe38bf5dea814894e2d8677fc903a3c8db49283086087c7` |
| Installed Python | SHA-256 `d932e5e2f324d57f392e8fd063dcf6d0185be8a664c57c6d24e7762ed02c28ca` |

The build used Windows x86-64 optimization level 2, full LTO, x86-64-v3, debug information, an unstripped executable, QOM cast checks, and assertions. The verified package also contains a separate DWARF image with `.debug_info` and `.debug_line` and an ordered symbol listing.

The retained same-host preflight identifies Windows 10 build 19045.6466, an AMD Ryzen 9 6900HX with 16 logical processors, and an NVIDIA GeForce RTX 3070 Ti Laptop GPU with driver 581.95. This identity was reused; no new hardware inventory or trace campaign was run.

## Unit results

| Execution | Result | Evidence |
| --- | --- | --- |
| Builder under Wine | PASS, exit 0 | Exact candidate build receipt |
| Windows native | PASS, exit 0, 10/10 TAP cases | stdout SHA-256 `477a5a19044d6dc67c4fe593c47392b98b9cfa75c356a8cd5ebf4b599292a2a8`; empty stderr SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |

The native unit covered exact DMA fits, incomplete and one-byte-short DMA spans, a nonzero-offset fit, the original incomplete span, an offset beyond the inclusive limit, exact and incomplete VRAM spans, a nonzero base plus offset at the VRAM end, and the complete three-word RAMIN descriptor preflight. Invalid spans performed no stores in these production-path unit controls.

The Windows unit ran once. The successful guest-matrix retry hash-validated and reused that receipt instead of executing the unit again.

## Renderer results

Each cell selected one exact report test ID. The installed runner was invoked in interactive Session 1 with scale 1, 64 MiB guest memory, vsync off, zero warmup iterations, iteration multiplier 1, per-iteration completion, host telemetry off, and no xemu environment overrides. Vulkan validation was enabled and active in all six Vulkan cells, with zero unique VUIDs. All twelve cells completed their terminal semaphore and returned one matching PASS record.

| Report control | OpenGL observation | Vulkan observation |
| --- | --- | --- |
| `zero_query` | PASS; complete A0 value 0 | PASS; complete A0 value 0 |
| `single_boundary` | PASS; complete A0 value 16,384 | PASS; complete A0 value 16,384 |
| `multiple_boundaries` | PASS; complete A0/A1 values 16,384 / 32,768 | PASS; complete A0/A1 values 16,384 / 32,768 |
| `clear_boundary` | PASS; complete A0/A1 values 16,384 / 16,384 | PASS; complete A0/A1 values 16,384 / 16,384 |
| `dma_target_switch` | PASS; complete A0/B0 values 16,384 / 16,384 | PASS; complete A0/B0 values 16,384 / 16,384 |
| `dma_range_guard` | PASS; complete A0 value 16,384; invalid A1 retained its range fill; complete later B0 value 0; canaries intact | PASS; complete A0 value 16,384; invalid A1 retained its range fill; complete later B0 value 0; canaries intact |

The DMA-range leaf supplies the bounded end-to-end result required here: a valid report before the invalid target publishes, the invalid A1 target and adjacent canaries remain unchanged, and a later valid B0 target publishes. Both renderers therefore demonstrate safe rejection and continued leaf progress on this exact candidate. The Vulkan candidate also resolves the previously observed leaf-level symptom in which B0 remained at its sentinel.

These observations do not establish the internal state at the exact retirement decision. In particular, they do not directly show FIFO GET equals PUT, a nonempty report queue, `in_command_buffer=false`, or query counters at the call to `pgraph_vk_process_pending_reports`.

## Explicit coverage gaps

The pinned 157-record image has no dedicated report-only, no-draw leaf. `zero_query` disables ZPASS counting but deliberately issues a draw, so its zero result is a valid publication control and is not a no-draw/no-active-command-buffer control. The range leaf has a later phase without a new draw, but it does not expose the renderer's internal command-buffer state and cannot replace the missing dedicated control.

The installed HostGDBSampler captures `info threads` and all-thread backtraces only. It has no existing breakpoint/expression hook for FIFO pointers, queue occupancy, `in_command_buffer`, query counts, or retirement outcome. It also requires a live measurement marker, while this ordinary Release used the reviewed missing-marker correctness waiver and the runner rejects combining that waiver with host GDB sampling. No new debugger framework or product instrumentation was added. Direct no-command-buffer state proof remains pending.

The invalid report policy remains a safe emulator choice demonstrated by these tests: diagnose, perform no report-memory write, retire the entry, and continue. Real Xbox error or notification behavior for this invalid command is unproven.

## Attempt history and method

The first dispatch used Windows PowerShell 5 and stopped at the named-pipe constructor before the inner runner. Retrying the dispatcher through the documented PowerShell 7 executable reached Session 1. The Windows unit passed, but all guest invocations then hit one common runner admission error before xemu launch: `--enable-xemu-only-tests` requires the `pfifo-packet-boundary` profile or a full-suite request. This is one infrastructure failure, not twelve product failures. Its receipt is preserved and sanitized separately.

The corrected attempt added the required profile while keeping every explicit `--test-id`. Installed-runner source confirms that an explicit test ID takes precedence when it builds the selected profile and exact test filter. Each returned summary was also required to contain exactly one record with the requested catalog ID, preventing packet tests from substituting for the report leaf. The retry used a new result root and did not rerun the native unit.

The six cells ran in this order for each renderer: zero result, single boundary, cumulative boundaries, clear boundary, DMA target switch, and DMA range guard. The invalid range leaf ran last. It was executed only on the fixed candidate; no unsafe invalid write was repeated on previous main, the frozen baseline, or a drain-only build. Automatic admission required no tracked xemu or WPT process and at least 6,144 MiB free memory before each cell.

The runner mode is named `perf`, but these records are correctness diagnostics. The ordinary Release lacks live markers, the missing-marker waiver was recorded in every summary, host telemetry was off, and guest durations are excluded from performance acceptance.

No baseline executable was rebuilt or launched. Historical context remains separate: previous-main SHA-256 `13f61e7655a7b37ea51c282335b7540b48e92dc5980af0877be2e968eb571d9a` is runtime-source-equivalent to the reviewed main state, while frozen baseline SHA-256 `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` is a distinct executable. Historical OpenGL showed terminal completion, later B0 publication, and changed range canaries; historical Vulkan retained the canaries but left B0 at its sentinel. Neither was rerun.

## Cleanup and transferable evidence

The successful receipt records the private suite HDD absent, no remaining owned candidate process, and no cleanup error. A separate post-run check confirmed no process whose executable came from the candidate deployment remained and reconfirmed the private HDD was absent. No WPT analyzer, ETL capture, benchmark, retail workload, full-suite run, or additional input campaign was started.

| Transferable artifact | SHA-256 |
| --- | --- |
| `native-results.json` | `34fd02d66da902c2dfd640c3bfd3bad1db3cbad3a14c5fb0ea402a573fef4faa` |
| `native-results-attempt1.json` | `a15ebf7711e90e7192cfaabf5232605e9e5a7c7fbb1209734ff0f4d9e5ccf2d6` |
| `native-attempts.json` | `3398e9f0bbf4dd3ee6b57069e21a27b3abcd514b546a1a4c10b3313a887aa53a` |
| `build-unit-receipt.json` | `19a17ce58bf911a1579e30d128c6176a1048efff089981c7118e3b131a547366` |
| `summary-reverification.json` | `66e52d0fb754caf566d381c9036fb1c2db000b3dbac8fa2f62d22fe093363aac` |

Private receipts retain per-cell storage locations. Public JSON retains the relevant records and their hashes.
