# PR74: report bounds and idle retirement

**24 current-head targeted cases PASS under Wine; release qualification still pending.** [Product PR74](https://github.com/Mainkill1/xemu/pull/74) repairs [issue60](https://github.com/Mainkill1/xemu/issues/60). This evidence branch covers PR74 only.

The retained native dataset below uses `05c149635b839e09bbe1c457f26f55ca4ad5be8b`, built from tree `f1479bd7e58371f8b03233b73bf239b93dd5a024`. Windows executable SHA-256: `9a08f60052d50ffc714baac85bbe6d8d4a25aeea4a623f0394b21d0c2342fb09`.

The shared writer validates the complete three-word descriptor read and all 16 destination bytes. The Vulkan queue retires at FIFO idle even without an active command buffer. Existing GPU completion, captured DMA ownership, cumulative counts and the three little-endian stores are preserved.

Current product head `e1ec62ede550b7ab7fdf92f1d866e8747703fd0e` now passes 16 serializer, two wrapper/decoder and six real Vulkan retirement cases under Wine. The exact full Windows build and diagnostic bundle are complete. [Targeted results, test boundaries and artifact hashes](targeted-tests.md) are separate from the retained native results below. Native and broader qualification remain pending.

## Retained native results

| Check | OpenGL | Vulkan |
| --- | --- | --- |
| Zero query | PASS: A0 = 0 | PASS: A0 = 0 |
| Single boundary | PASS: A0 = 16,384 | PASS: A0 = 16,384 |
| Multiple boundaries | PASS: A0/A1 = 16,384 / 32,768 | PASS: A0/A1 = 16,384 / 32,768 |
| Clear boundary | PASS: A0/A1 = 16,384 / 16,384 | PASS: A0/A1 = 16,384 / 16,384 |
| DMA target switch | PASS: A0/B0 = 16,384 / 16,384 | PASS: A0/B0 = 16,384 / 16,384 |
| DMA range guard | PASS: A canaries intact, B0 = 0 published | PASS: A canaries intact, B0 = 0 published |

All 12 selected tests completed and returned exactly the requested record. Vulkan validation was active with zero VUIDs. The final production serializer unit passed under Wine and passed 10/10 natively on Windows. The native unit ran once; the corrected guest invocation reused its verified receipt.

The original OpenGL symptom was changed A canaries; the original Vulkan symptom was an unpublished later B0 with intact A canaries. The candidate fixes both observed leaf-level symptoms. B is a separate requested buffer; its valid zero value after clear is not corruption. Invalid-span execution was restricted to the repaired candidate; historical failures remain the reference and neither baseline was rebuilt.

## Limits and remaining gates

These are correctness diagnostics, with scale 1, 64 MiB guest memory and VSync off. The missing-live-marker waiver was explicit. No FPS, frame-tail or resource improvement is claimed, and a timeout becoming successful is not a performance improvement.

The existing zero-query fixture still draws. The results do not directly establish the command-buffer state at retirement; a dedicated no-draw/no-active-command-buffer control remains pending. The descriptor predicate and valid guest path are covered, but native malformed-descriptor-wrapper coverage is not claimed. Hardware behavior for invalid report commands remains unproven.

Full XISO, query-capacity/vertex ownership, PGR2 fresh-start and snapshot, Morrowind snapshot, and matched normal-path resource/frame-tail comparisons remain acceptance gates. Candidate versus previous main and versus the fixed baseline must be reported separately, with positive Improvement% favorable. No merge or baseline change follows from this focused dataset alone.

## Preserved unsuccessful attempts

Two build links failed from ENOSPC; the successful build used the same source/options with bounded temporary storage. The first dispatcher failed before reaching the inner runner. After using the documented PowerShell version, a shared runner argument error stopped every guest invocation before xemu launched. The corrected attempt retained exact test IDs, added the required diagnostic profile, and checked returned IDs/counts. These are infrastructure failures, not product test failures. [Build outcome](build-outcome.md) and [native validation](native-validation.md) retain the details.

## Reproduction and records

Use the pinned runner and image from [planned-manifest.json](planned-manifest.json), exact candidate/build from [build-unit-receipt.json](build-unit-receipt.json), and settings in [native-results.json](native-results.json). For each report ID in the table, select that exact ID using the runner's `--test-id`; the installed runner also requires `--profile pfifo-packet-boundary` with `--enable-xemu-only-tests`. Explicit test ID takes precedence, and one matching returned record is required. This diagnostic invocation is not a performance run.

- [Detailed native report](native-validation.md), [per-test CSV](focused-results.csv), [complete sanitized records](native-results.json).
- [Preserved runner admission failure](native-results-attempt1.json), [independent summary rehash](summary-reverification.json).
- [Build profile and artifact hashes](build-manifest.json), [build/unit receipt](build-unit-receipt.json).
- Verify the public records with `python3 check-native-results.py native-results.json`.

All owned test processes closed and the temporary test disk was removed. Matching DWARF and symbols are retained for diagnostics. The staged current 157-record XISO is reused; no new image is claimed. Raw build logs and private storage locations remain outside source history.

## Review follow-up

The [checker correction](checker-review.md) now rejects incomplete result publication, overwritten B1 sentinels, and ID/scenario mismatches. Seven new checker tests pass, and the original 12 native records remain unchanged and accepted.

The original 4,097-draw query-pressure fixture has also been restored to the maintained suite. [Provenance and required run settings](query-control-provenance.md) preserve attribution and the original oracle. Current catalog now has 158 records (153 leaves, five groups), ID `sha256:77c8b75d5eb9c4b2a6d830581e7f239b0fd7a041c569877676c286f89d0b424a`. Existing profile changes only refresh generated catalog/plan identities. No new XISO or guest result is claimed yet; all earlier records above still refer to their original 157-record image.

PR74’s expanded serializer, wrapper/decoder and real Vulkan retirement tests now pass under Wine at `e1ec62ede5`. [Current targeted evidence](targeted-tests.md) includes each TAP record and the build receipts. The native results above retain their original source and test-image identities.
