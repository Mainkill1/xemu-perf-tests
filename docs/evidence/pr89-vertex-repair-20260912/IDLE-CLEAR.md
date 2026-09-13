# PR87 idle read-page clear: focused repair qualification

This record supersedes the #87/#89 source identities in [the earlier reconciled report](RECONCILED.md). That report and its prior-head results remain retained for comparison. The current product heads are draft #87 `ea27c47d35cfd21cfe5178c30c25467a748eaa48` and draft #89 `d8621e7494e87304e607cf54a5ec89917275ed70`; #85 remains `0883fb63009c6cc804681cbdb39e4454b44d8456`.

The prior #87 finish path cleared the full `vertex_ram_read_pages` bitmap on **every** command-buffer finish, including quiet batches with read tracking inactive. The bitmap starts zeroed and is cleared on the last active finish before tracking retires. The focused change conditions the clear on active tracking, preserving all active-batch behavior. #89 incorporates it via a normal merge, without rewriting prior history.

| Product | Source tree | Win64 O2/LTO executable SHA-256 | Exact-source build and focused units |
| --- | --- | --- | --- |
| #87 | `b11da0fd59e09ac02b100aa2a28ef4e3a58a0bc4` | `131a17325bba0135f357b2c463cc6b6787a1f63b2a075be8883d1501a570d536` | Build PASS; fetch span 2/2 |
| #89 | `244e62d51559fa649177248492ba9384e8e8693e` | `1bd950da8ceabe715a56cf982cf955aa165283221ee5d1a6209042215bd27c92` | Build PASS; fetch span 2/2; version policy 3/3 |

The pinned GCC 16.1.0 Win64 image was `sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`. All 11,404/#87 and 11,406/#89 regular tracked source files matched the exact Git trees before and after linking; the Vulkan `draw.c` object rebuilt in both. The executable hashes were checked again on the Windows test host before running the units. No runtime timing result for these updated binaries is claimed yet.

## Trigger and negative control on the previous head

A diagnostic PGR2 snapshot pair on previous heads [#87 `b3b99fb` and #89 `150d74a`](results/diagnostic-pgr2-version-path.json) recorded zero vertex-version selections/draws and zero vertex-staging copies in both cells. The adverse #89 p99 therefore was **not** shown to be caused by actual version copying. The PGR2 scene did have roughly 17 command buffers per guest frame; the unguarded read-bitmap clear ran after their completion regardless of whether tracking was active. This is source-confirmed redundant work, not yet a measured causal explanation for the full tail difference.

The [previous #85 → #87 PGR2 snapshot ABBA cells](results/pre-idle-clear-pr85-pr87-pgr2.json) used 30-second warmup and 60-second Vulkan measurement. Positive Improvement % is better for lower guest-frame interval.

| Run order | #85 / old #87 p95 | p95 Improvement | #85 / old #87 p99 | p99 Improvement |
| --- | ---: | ---: | ---: | ---: |
| #85 → old #87 | 38.341 / 39.369 ms | **−2.68%** | 42.705 / 43.896 ms | **−2.79%** |
| old #87 → #85 | 38.771 / 38.964 ms | **−0.50%** | 42.887 / 43.743 ms | **−2.00%** |

The prior #87/old #89 full XISO hashes and outcomes, Morrowind fixed-scene gain, and PGR2 full-start cap result remain useful historical evidence, but they do not qualify this updated exact stack.

## Remaining gate

- [ ] Matched new #87 versus old #87 PGR2 snapshot, then new #89 versus new #87.
- [ ] Current-head three-generation, XISO, and Morrowind qualification after the inherited change.
- [ ] Direct GPU-surface-to-vertex and version finish/rollover/stale-repair oracles, cross-platform checks, and independent review.

Do not merge while the PGR2 tail and those correctness gates remain unresolved.
