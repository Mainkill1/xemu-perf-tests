# Add or extend a test

## Required contract

Every new executable result needs:

1. A deterministic workload with fixed generated input.
2. A stable lowercase ID and revision in the catalog descriptor source.
3. One exact legacy suite/result mapping.
4. A useful description: operation, xemu path, and failure meaning.
5. Tags, target support, isolation, timeout, and measurement class.
6. At least one correctness observation: result checksum, narrow KAT, or
   framebuffer hash. Performance-only output is insufficient.
7. An explicit timing boundary and completion policy.
8. Registration in the appropriate `src/tests/` suite.
9. Contract tests for counts, ordering, masks, and known answers.

Do not use retail assets. Generate input from a fixed seed or embed open data.
Expected output may come from retail Xbox hardware, an independent
specification, or an explicitly labeled regression oracle.

## Leaf versus group

A leaf performs work and may contain measurements. A group only describes and
selects children. Groups use `aggregation=none` unless a real scenario-wall or
sum contract exists; they must never copy the last child's timing.

Composite children need a unique selection bit. Bits are interface values, not
arbitrary tuning constants: document the mapping, assert uniqueness, and test
every valid subset used by automation.

## Implementation steps

1. Add or extend the workload in `src/tests/`.
2. Emit results through `FinishDraw` or `RecordProfileResult` using the exact
   registered suite/result name. Use `FinishGroup` only for structural parents.
3. Add its descriptor to `utils/test_catalog.py`'s maintained inventory.
4. Regenerate catalog artifacts:

   ```bash
   python3 utils/test_catalog.py
   ```

5. Inspect `resources/catalog.json` and
   `docs/generated/test-catalog.md`. Do not manually edit them.
6. Add focused host contracts under `tests/`.
7. Run:

   ```bash
   python3 utils/test_catalog.py --check
   python3 -m unittest discover -s tests -p 'test_*contract.py'
   ```

8. Build the Release XISO with the pinned NXDK revision.
9. Run the focused leaf, its containing group, and a full correctness suite.
10. Compare OpenGL/Vulkan and 1x/4x when the path is renderer- or scale-sensitive.

## Known-input/known-output rules

- Hash/check generated source bytes before submitting work.
- Keep work/result checksums separate from framebuffer hashes.
- Place validation outside the timed body unless validation is the operation.
- Preserve raw timing samples; do not hide failures as statistical outliers.
- A failed sample remains failed even if a retry passes.
- Record the first failure and continue only when the test is explicitly safe
  to continue.
- Never update a golden merely because new xemu output is stable.

## Performance rules

- Correctness first: identical work and result oracles are mandatory.
- Measure seconds, not nanoseconds. Batch short operations while preserving the
  operation count.
- Use excluded warmups and at least repeated interleaved A/B processes for a
  claim.
- Record median, p95, dispersion, and every raw sample.
- Separate guest timing from host CPU/GPU attribution.
- Explain every capacity or threshold. If a value is empirical, test nearby
  values and retain the result.

## Review checklist

- Stable ID cannot collide or change silently.
- Revision changes when semantic work or observation scope changes.
- Catalog generator and all contracts pass.
- Resolved-plan leaf count exactly matches emitted leaves.
- No group advertises fake timing.
- Hash/KAT mismatch, timeout, crash, and VUID are visible failures.
- Release manifest records commit, image SHA-256, NXDK revision, expected
  records, and oracle provenance.
- README/catalog documentation explains what the test attacks and what failure
  means.
