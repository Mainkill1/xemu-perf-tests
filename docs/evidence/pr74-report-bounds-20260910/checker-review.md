# Native-results checker review

`check-native-results.py` now validates the report-publication contract using
the fixed guest constants in `src/tests/report_query_tests.cpp`:

- timestamp sentinel: `0xF00DFACECAFE0123`
- value sentinel: `0xDEADBEEF`
- done sentinel: `0xA5A55A5A`; published done value: `0`

Each of the twelve expected cells is bound to its ordered backend, stable test
ID, and guest scenario. Published records require a changed timestamp, a value
other than `DEADBEEF`, and `done == 0`. Every B1 record must remain the full,
unchanged sentinel record.

The new synthetic regression suite first failed against the prior checker:
it accepted a published `DEADBEEF` value, a changed B1 record, a stale A0
timestamp hidden by changing B1, and a stable-ID/scenario mismatch. The
corrected checker rejects all four mutations and a direct stale-timestamp
mutation, while accepting the unmodified published result.

Validation:

```sh
python3 -m unittest tests/test_pr74_native_results_checker.py
python3 docs/evidence/pr74-report-bounds-20260910/check-native-results.py \
  docs/evidence/pr74-report-bounds-20260910/native-results.json
```

Both commands pass. The regression suite uses temporary synthetic copies only;
the native result, failed attempts, profiles, hashes, and shared `REPORT.md`
were not edited. This checker validates recorded evidence and does not replace
the remaining native renderer, full-catalog, or performance gates.
