# PR70 focused SPIR-V prewarm admission

**Result: PASS for the focused functional gate. Full performance qualification remains pending.**

Candidate `b14bfb745870faae500a1ecb0ff49d2143ba8bd1` (tree `3a79dd692d9e7f1089fa0b138d07fc4269fbd704`), xemu SHA-256 `d6c0762fd672932667537b7152bf4068a7c313d2980d4b545e020e852064bc9d`. The focused native test exited 0.

## Cache behavior

| Cell | Seed | Hits | Misses | Rejections | Loaded | Queued | Shutdown |
|---|---:|---:|---:|---:|---:|---:|---|
| cold | 0 B | 20 | 121 | 0 | 0 B | 3,038,601 B | published |
| warm | 3,042,552 B | 140 | 0 | 0 | 3,042,552 B | 0 B | clean |
| corrupt-recovery | 16 B | 20 | 121 | 1 | 0 B | 3,038,601 B | published |

Cold published 121 records in a 3,042,552-byte file. Warm loaded the byte-identical cold artifact, produced 140 hits and zero misses, and did not rewrite it. The corrupt cell started from a 16-byte truncated copy, rejected it once, compiled normally, and replaced it successfully.

## PGR2 snapshot metrics

| Cell | FPS | Average | p95 | p99 | Max | ≥75 ms stalls | Avg improvement vs baseline | p95 improvement vs baseline | p99 improvement vs baseline |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cold | 29.122 | 34.327 ms | 41.060 ms | 45.732 ms | 58.383 ms | 0 | +0.456% | -0.367% | -1.208% |
| warm | 29.102 | 34.380 ms | 41.141 ms | 46.424 ms | 55.858 ms | 0 | +0.301% | -0.565% | -2.740% |
| corrupt-recovery | 28.958 | 34.527 ms | 41.232 ms | 47.021 ms | 78.188 ms | 1 | -0.125% | -0.787% | -4.061% |

Improvement percentages use positive-good semantics. For interval metrics, `(reference - candidate) / reference × 100`. The reused published baseline is average 34.483841 ms, p95 40.910 ms, and p99 45.186 ms from baseline ref `9f618d6d8c4c446ef023955f3d4de22f661f61a4`; it was not rebuilt.

These are single candidate cells against a historical baseline, so they do not establish a performance pass. Warm p99 is -2.740%, outside the 2% band. The planned paired full qualification remains required.

## Admission and cleanup

All three accepted captures showed an active PGR2 race with the expected car, HUD, and track. Guest frames, guest flips, and host presents progressed; focus loss and nonresponsive samples were zero. Every xemu instance closed normally, every writable HDD clone was deleted, the immutable seed hash remained unchanged, no WPR/ETL session ran, and no owned helper process remains.

One earlier cold attempt was excluded when SDL ignored an APPDATA-only isolation attempt. The owned cache it created in the normal profile was removed. The accepted cells use xemu portable mode with byte-identical executable copies and separate cache roots. Raw logs and screenshots remain on the authorized test host.
