# Historical query-pressure control provenance

This repository restores the historical `QueryPressure::query.repeated-page-4097`
guest control as a qualification fixture. The recipe originates with Mainkill1's
commit `dda08125e0e74fe8400614da096a6a3b2c3fa7ac`, **ENG-2026-523 Test: Use
report DMA in-memory class and describe query oracles**. This restoration keeps
the original 4,097 draws, recipe FNV-1a32 `0xC4DDD0FB`, expected accumulated
ZPASS `655424`, and 512 final tile checks.

The archived Issue50 receipts identify test-image source
`dda08125e0e74fe8400614da096a6a3b2c3fa7ac` and image SHA-256
`6c307c997d7de21cdbdfe7ea5554a3bd9b011d979c5568ad14dbfe33a292cf7e`.
They record the oracle result as 655,424 samples, zero tile mismatches, and
framebuffer FNV-1a64 `89ccbb563c63e0a5`.

The archived Vulkan receipts use `staging_mib` 4, 8, and 16. The current
product still parses the corresponding setting from
`XEMU_VK_VERTEX_STAGING_INITIAL_MIB`; it accepts exactly 4, 8, or 16 and uses
8 MiB for an absent or invalid value. A future matrix run must explicitly pin
that setting, use the rebuilt fixture image, and record its own executable and
image hashes. This restored source must not be described as the historical
binary or ISO.

The only source-level adaptations are required by the current APIs: the guest
uses `DMA_CLASS_3` in place of the historical `DMA_CLASS_3D` spelling, and DMA
context 23 avoids the current ReportQuery suite's 20--22 contexts. These
changes do not alter the draw count, recipe, report order, or known answers.
