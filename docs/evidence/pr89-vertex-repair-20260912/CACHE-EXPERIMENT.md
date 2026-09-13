# PR #85 overlap-cache experiment: build identity and PGR2 result

The cache-only experiment is **not qualified for merge**. It reduced the
measured p95 in both comparisons with the prior #85 head, but one of three
direct comparisons with current `main` had substantially worse frame pacing.
A source audit found a simpler redundant-work path that the cache does not
remove: #85 scans the active surfaces twice and forces a vertex-mirror upload
for clean surface overlaps. That path is being repaired separately.

| Role | Exact source | Win64 executable SHA-256 |
| --- | --- | --- |
| Current `main` control | `9148241de690617ac0a21a26b41858585c1e3cab` (same tree as tested `6bf9e98`) | `6857240d6e95909d591832685c60e376611924d00a9688da4d7d2b89e84c17f6` |
| Prior #85 | `8d9245ddeb5f13d23a5e3f2aafdb5144c4bdad30` | `0c0e11d66e5a2b0b75fad38c8bb5acf88b5291b1115a47c6ba501f262fce313d` |
| Cache experiment | `9e97dcb9b3a419a930c54688008f281b32de1d42` (tree `8bfcc40a1a447ac31f1e1eb2b1f99c4527622724`) | `f8faf95af8b222794447aa4cbe8bad871f8903ba23e06701150d7d5a74c1d1b7` |

The cache build used pinned Win64 GCC toolchain image
`sha256:09fdc183a88b493bf3a98d0d00b03aca4d5a23e60cc08228d7752d3c3295e8b2`
with `-O2`, full LTO, x86-64-v3, debug information, and assertions. All
11,417 regular tracked source files matched the exact head's hashes before
and after linking; changed Vulkan objects were recompiled. The dedicated
Win64 cache-policy unit passed. The capture runner's optional
`source_ownership_valid` field remained false because these runs did not
provide its build-manifest/PDB pair; that flag is not the independent
whole-source hash check just described.

Each PGR2 Vulkan snapshot cell used the same saved state, seed HDD,
configuration hash, scale 1, 30-second warmup, and 60-second measured window.
All cells completed with zero focus-loss or unresponsive samples and no
tracing. Positive **Improvement %** means a lower guest-frame interval.
Per-cell metrics, identities, and health fields are in
[the compact result record](results/pr85-overlap-cache-pgr2.json).

| Matched order | Mean Improvement | p95 Improvement | p99 Improvement | Guest frames control → cache |
| --- | ---: | ---: | ---: | ---: |
| Prior #85 → cache | +0.04% | +1.65% | +1.35% | 1,771 → 1,773 |
| Cache → prior #85 | +0.09% | +0.28% | -0.06% | 1,774 → 1,776 |
| Main → cache | -0.03% | +0.25% | -0.13% | 1,776 → 1,776 |
| Cache → main | **-2.37%** | **-5.83%** | **-3.49%** | 1,776 → 1,735 |
| Cache → main confirmation | +0.22% | +1.92% | +1.82% | 1,774 → 1,780 |

The adverse cache cell began measurement at guest-frame ID 1,292; the
other four direct-main cells began at IDs 1,328–1,330. Its lower frame count
is not solely a different window over the scene: aligning all four ABBA
captures to the same 1,697 guest-frame IDs (1,330–3,026) still leaves that
cell **0.822 ms/frame slower** than its paired main control. The following
confirmation cell favored the cache. We have not attributed this isolated
slow run to the patch, host state, or game-state timing, so the record cannot
support a stable win or a causal regression claim.

The main/control binary matches the intended main source tree; PE/DWARF
producer records show the same GCC 16.1 `-O2`/LTO/x86-64-v3 profile as the
candidate. Historical overlay builds verified changed source files and
recompiled changed Vulkan objects, but did not capture a whole-tree digest
for every link. The cache candidate closes that attestation gap. The evidence
does not support a wrong-compiler or wrong-merge explanation for the prior
#85 p95/p99 result.
