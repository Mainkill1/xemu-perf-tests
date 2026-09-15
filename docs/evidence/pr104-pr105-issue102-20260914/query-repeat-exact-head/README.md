# PR104/PR105 exact-head report-query repeat

This focused Windows campaign repeats the three report-query records that differed in the earlier full-suite run. It uses the unchanged XISO source `57c2438c3d46c8f99bc18004f1fd34a5d9ed82b9`, ISO SHA-256 `6a57961a7312bb8ec125181ac5e642d194835df382cbb900c81efaf9765536cd`, and catalog SHA-256 `ea881a43ec71cc37f74e5863e00f0cf4caea94e32933a5a15063e179e743ddfb`.

All cells ran natively on the Windows RTX 3070 Ti test host with Vulkan, 4× scale, shader cache Off, Hybrid On, and shader shortcut On. Each role/test pair ran three times as a fresh process. Optional live markers were unavailable, so timing remains diagnostic; the PASS/FAIL guest outcome is retained.

| Role | Source | Executable SHA-256 | `zero_query` | `clear_boundary` | `dma_range_guard` |
| --- | --- | --- | ---: | ---: | ---: |
| Previous main | `322986f4c5502b3fa887a9605ac8cd88e9b2c579` | `992c5cf7bb25ccfd7d6384ee837c051b31120d227cbc6e0febe8207790e0023e` | 3/3 PASS | 3/3 PASS | 0/3 PASS |
| PR #104 | `d89cbb3d54eb168f0e005b8cb4e35e36f864babf` | `5f79b6d5bf20ce24d8b1e4f0ff7e18e168773ffc7f32ee8fdcaf60f23e0e1401` | 2/3 PASS | 3/3 PASS | 0/3 PASS |
| PR #105 | `0f45e35b32a622da781dc5c4b8e4740e15b0a268` | `a76b68fcb9cb8c09258843c1780e48a97d23f53a7bb5ac5097fd02b864c56aab` | 3/3 PASS | 3/3 PASS | 0/3 PASS |

The earlier full-suite failures do not follow either patch. `clear_boundary` passes every exact-head repeat, `zero_query` changes outcome across executions of PR #104 and had previously failed unchanged main, and `dma_range_guard` fails identically on every role. The remaining report-query work belongs to the test/report subsystem; it is not evidence that PR #104's copy setup or PR #105's staging/shader bounds introduced a regression.

[Raw normalized cells](results.csv) retain repeat, source, executable, outcome, exit code, and elapsed time. Logs with host paths and transient window-attachment diagnostics remain private on the test host.
