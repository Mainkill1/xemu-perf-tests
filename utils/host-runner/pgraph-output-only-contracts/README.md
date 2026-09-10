# PGRAPH output-only contract recipes

These schema-1 recipes select the one catalog leaf
`busy_pfifo.pgraph_pattern_polling` (`BusyPfifo::PgraphPatternPolling`,
revision 1) for the pinned 442ec11 test image/catalog identity recorded in
each file. They use four measured iterations, one raw sample, the existing
framebuffer FNV-1a64 `386d0f085e98c325`, and the existing 15-second measured
and 5-second warmup floors.

`metadata: null` has a narrow serialization meaning: the normalized record
must **omit** the `metadata` member. It does not accept a record containing
`"metadata": null`, an empty object, or a different object. The PGRAPH guest
calls `FinishDraw` without metadata, and the host serializer writes that
member only for a nonempty metadata string. The pinned child normalizer
shallow-copies raw records and fills timing fields only, so it preserves that
absence. This corrects the earlier admission-note wording that implied the
normalizer inserts null.

Apply both digest-pinned patches only to their stated inputs:

- `run-suite-output-only-null-metadata.patch` targets child SHA-256
  `c478e3a38865de180f3751b88904bf18b152dd05208e773326979e3d7b65b64d`;
  its patch SHA-256 is
  `1b6486e7a8d93b4c3e86fe35adb37728c16cad771fdcf0e8821cb38589f931b5`
  and its result SHA-256 is
  `7bc444093728671ccc6e5cbca1111ff8fef2f673b4a6b8e6a2e335ccb1287340`.
- `run-pair-output-only-forwarding.patch` targets pair SHA-256
  `e358b55d940e361bf57ef64a7a5cde83fc267d885191c813e7616764a88ee58a`;
  its patch SHA-256 is
  `f1c2b17f31de7cf1903f6a8ef9871e9b7103b7276085591dfc76484df36a46d0`
  and its result SHA-256 is
  `ac61d8d75dcbffbdce712a60e293a39eded955d1ddcb8986df94037451e59e99`.

The pair forwards `--guest-evidence-mode` and the contract path to every
sequential child. In output-only mode it rejects marker compatibility,
compatibility allowances, ledger disabling, short-smoke floors, non-off host
telemetry, missing child output validation, and a child contract digest that
does not equal the requested recipe's digest. The pair receipt records the
mode and contract path/digest.

The recipes provide source/artifact identity and strict post-run correctness
rules. They are not a baseline calibration, a native execution receipt, a
live-marker substitute, a full-XISO result, or a performance comparison.
