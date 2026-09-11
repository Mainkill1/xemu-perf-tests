# PR74 targeted production-path qualification

**All 24 targeted cases pass under Wine at product commit `e1ec62ede550b7ab7fdf92f1d866e8747703fd0e`, tree `8b34a2a6115246a42799f7f927933e50a413751d`.** The full Windows executable also builds and has been deployed with matching DWARF and symbols. Native execution, refreshed-XISO and retail/performance gates remain pending. The earlier native results at `05c149635b` remain a separate dataset.

| Target | Cases | Completed execution | Evidence |
| --- | ---: | --- | --- |
| Production serializer | 16 | Wine PASS, exit 0 | [TAP](targeted-e1ec62ed/test-xbox-pgraph-reports.tap.txt) |
| Production wrapper → decoder → serializer | 2 | Wine PASS, exit 0 | [TAP](targeted-e1ec62ed/test-xbox-pgraph-report-wrapper.tap.txt) |
| Production Vulkan pending → finish → retirement | 6 | Wine PASS, exit 0 | [TAP](targeted-e1ec62ed/test-xbox-pgraph-vk-reports.tap.txt) |

The serializer checks exact fits and rejects incomplete DMA/VRAM spans, including the base/offset guards and maximum unsigned values. Rejected operations preserve the entire owned buffer; accepted writes preserve the entire prefix and suffix. The wrapper executes the actual decoder with both an incomplete descriptor before protected memory and a valid descriptor at the boundary.

The Vulkan cases seed a nonzero accumulated count without a command buffer, exercise clear/report ordering, reject a destination and later publish through a valid DMA context, preserve nonidle deferral, and check descriptor decoding at retirement. The first case also repeats processing after the queue empties and requires no extra finish/publication. The active-command-buffer case supplies a pending query, observes the real submission/wait path and query retrieval before publication, and checks the accumulated result. No-command-buffer cases require zero GPU submissions.

## Test boundaries

The tests link the maintained production translation units. They do not replace `pgraph_vk_finish()` or the queue drainer. Vulkan/VMA boundary calls are instrumented, the MemoryRegion size query is an owned-buffer test shim, and full QOM/device realization is outside scope. A test-only header suppresses an unrelated device-registration constructor so section collection can discard the untested device closure. A memory-budget branch is an explicit failing unreachable guard, not an emulated success.

The DMA-context case models retirement before changing the context; it does not dispatch the static context-setting method. The active-query case models an already-issued query and tests its completion, not query creation. These are production-function tests rather than native GPU validation or game benchmarks.

## Build and preserved development failures

The [unit receipt](targeted-e1ec62ed/verified-units.json) pins each executable hash, source/tree and toolchain. The [full build receipt](targeted-e1ec62ed/verified-build.json) records the executable, DWARF and symbols, with O2/full LTO, x86-64-v3, assertions and debug information. Its `windows_units` field refers to Windows executables run under Wine; it is not a native-Windows execution claim.

All 854 unit compile/link steps and all 1,876 full-product build steps passed. `.debug_info` and `.debug_line` were verified. The deployed bundle was independently hash-checked. Neither reference executable was rebuilt.

Earlier attempts are retained privately: build staging/mount and archive-name failures, a missing existing header dependency, an unrelated device-registration link root, a Meson syntax error, and oversized stack fixtures. At `dbb9981b` all targets linked and the serializer passed, but both integration executables overflowed the Windows stack before TAP. Commit `e1ec62ed` moves only the large fixtures to owned heap storage and cleans up leftover queue entries. These harness/build failures are not xemu runtime failures. The review follow-up changes production files only through comments.

## Remaining acceptance

- Run these same executable identities once natively on Windows.
- Build and identify the restored 158-record XISO, then run both renderers and the 4,097-draw query control with the specified staging sizes.
- Complete vertex/report regression coverage, PGR2 fresh start and snapshot, and Morrowind snapshot.
- Report normal-path performance and resources against both previous main and the fixed baseline, preserving adverse tail results and incomplete gates.

PR74 remains draft. No performance improvement or release qualification is claimed from these tests.
