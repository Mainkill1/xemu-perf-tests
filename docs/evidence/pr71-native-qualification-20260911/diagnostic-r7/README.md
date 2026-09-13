# PR71 required-compile isolation: focused control

This record qualifies only the hybrid compiler's scheduling and teardown behavior at product head `601361bf82fe0214fcf900bdbbb866d081ecf038`. It is not a gameplay performance result or a cold-tail attribution.

| Identity | Value |
| --- | --- |
| Product parent | `48059eaea0d6203013bf409ecb926b092a692ee8` |
| Product candidate | `601361bf82fe0214fcf900bdbbb866d081ecf038` |
| Build source | Parent source plus the exact `parent..candidate` patch; tracked diff checksum `3fd88881f3219f700f2ad6218235ba0de45ce5e3d322e8b98b109293e6878690` (SHA-256 of `git diff --binary`) |
| Toolchain | Pinned xemu Win64 GCC image `sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2` |
| Test runner | Wine, isolated prefix; focused Win64 unit executable |
| Product executable SHA-256 | `eb17773b29423b091095afe230f76ee3ca1db618b5a383c6a7b0de4cb01cbe11` |

| Test | Parent with new test | Candidate | Meaning |
| --- | --- | --- | --- |
| Hold asynchronous compile; submit required compile; check it starts before background release | FAIL: `started` false after a one-second wait | PASS | Previous single worker caused head-of-line blocking; required lane removes that dependency. |
| Stop while required compile is active | Not run on parent | PASS | Caller receives stopped result; worker joins after held compile is released. |
| Full hybrid compiler unit executable | 7 prior cases plus failing new control | PASS 9/9 | Queue limits, deduplication, ownership, failure, and shutdown still pass. |
| Win64 product build | Not rerun for parent | PASS | Candidate compiles and links. |

The candidate build used the existing O2/full-LTO/x86-64-v3 Windows build configuration. The isolated build tree was compared with the candidate by hashing the complete tracked diff from the same parent. No production timing, full XISO, PGR2, or Morrowind run was performed at this head. The existing 81–85 ms cold spikes remain unattributed; pipeline readiness and draw-thread pipeline construction remain separate merge gates.
