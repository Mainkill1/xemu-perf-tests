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
  `fa75c44647f4db7c0b5c507e7fb30237c788e3205f19453ade896895ad7b705a`
  and its result SHA-256 is
  `fa6f714ee31a89eaabc44719f2b1057b9c75869c2264e5acaf78f81e74b4b608`.
- `run-pair-output-only-forwarding.patch` targets pair SHA-256
  `e358b55d940e361bf57ef64a7a5cde83fc267d885191c813e7616764a88ee58a`;
  its patch SHA-256 is
  `bfc2c68a70c6f68544ed954af8daf20a062ac426317582c589d106591189aaf8`
  and its result SHA-256 is
  `7e1a7ccc3fefc259775bffb5ba3198f05b3549b511ca4f342195b07716850e0e`.

The pair forwards `--guest-evidence-mode` and the contract path to every
sequential child. In output-only mode it rejects marker compatibility,
compatibility allowances, ledger disabling, short-smoke floors, non-off host
telemetry, missing child output validation, and a child contract digest that
does not equal the requested recipe's digest. The pair receipt records the
mode and contract path/digest.

The child requires the identity object, verifies its own patched digest, and
then verifies the selected guest ISO and discovered catalog digest/ID before
launch. The pair requires the same identity, verifies its own patched digest
before children start, and rejects child receipts without matching validated
identity. They are not a baseline calibration, a native execution receipt, a
live-marker substitute, a full-XISO result, or a performance comparison.
