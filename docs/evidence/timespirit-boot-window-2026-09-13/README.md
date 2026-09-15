# TimeSpirit: 10-second post-boot frame cadence

The original TimeSpirit image settled near 20 guest frames/s on the fixed
Windows/NVIDIA xemu configuration. A title-side patch now draws the body from
the existing 16-bit mesh indices, skips appendage skinning for vertices with
no appendage weight, and uses short, distinct names in the continuously drawn
menu line. The final full-file image produced 287 guest frames in 10 seconds
(about 28.7 frames/s). This is a TimeSpirit result, not an xemu optimization.

| Guest-frame metric | Original control | Final full-file image | Improvement |
| --- | ---: | ---: | ---: |
| Complete frames / 10 s | 200 | 287 | +43.5% good |
| Mean interval | 49.997 ms | 34.727 ms | +30.5% good (lower) |
| P95 interval | 50.057 ms | 49.997 ms | +0.1% (neutral) |
| P99 interval | 50.129 ms | 50.034 ms | +0.2% (neutral) |

The average improves because more frames meet the second VBlank. Some still
take about 50 ms, so this does not establish a frame-tail improvement. These
are guest flip intervals; host-present FPS was unavailable in this capture.

## Mechanism and source

The title updates 3,283 unique vertices and previously copied them into
17,136 triangle corners every frame. `NV097_ARRAY_ELEMENT16` now draws the
body from the existing index data. Shatter duplicates still use their own
vertices. The title validates indices once on load and keeps each nonincrementing
pushbuffer packet below the pbkit block-size recommendation. Appendage-weight
masks are prepared on load, so zero-weight vertices skip skinning and influenced
vertices visit only their actual bones. The full animation labels remain in the
title data; only the always-visible menu display uses shorter unique labels.

Apply [the title patch](timespirit-title.patch) to the source whose `src/main.c`
SHA-256 is `628ab9abad88cc979f8eb8a4c2dac777b29bbd0c1a39d993a54f8c64ed9ddeb9`.
The patched source SHA-256 is
`fbf0693b5477228ba749db136ea5e6313a8aacedcd7d5f12ca5724077f051d75`.
The original ISO SHA-256 is
`833207d56200e577e79da13ce229c4f240c6f3c05b3e966dd2e2fe5fe11f2c31`;
the final full-file ISO SHA-256 is
`61df846cbed0ddecff06fac27a359330681925f7869b8bf6bed4058d44cdd56f`.
The final XBE SHA-256 is
`54787b45fd7ef4e5fef1274f10bf8e4d00d76cff892c4c5cfca08b5f348566e2`.
The full-file image retains the original image's non-runtime files; its XBE and
eight required runtime assets were checked against the tested small image.
No ISO or proprietary assets are included here.

## Reproduction identity

| Item | Value |
| --- | --- |
| Emulator source | `aa260e72c51ebca05038a7abd0455f18e8c42084` (PR #89 diagnostic head, unchanged across title comparisons) |
| Emulator executable SHA-256 | `92abb1cc287d9a025b2bedb7f1146daf27f2305ff9f7f62bee85efe850390bfb` |
| Builder | NXDK; Debian clang 19.1.7 |
| Host | Windows 10 Pro build 19045; AMD Ryzen 9 6900HX; NVIDIA GeForce RTX 3070 Ti Laptop GPU, driver 32.0.15.8195 |
| Renderer | Vulkan, surface scale 1, NVIDIA adapter |
| Procedure | Fresh boot; 25 s warmup; 10 s measurement; identical emulator/configuration and HDD seed; no trace or Vulkan telemetry during comparison |
| Input | The capture runner sent `Q-1` one second into boot to satisfy its nonempty input requirement; the title remained at the menu |

The original control was repeated after the first candidate run and again
measured 200 frames. The short-menu candidate measured 287 and 289 frames in
two small-image runs. The final full-file image measured 287 frames. Individual
sanitized intervals are in [frame-intervals.csv](frame-intervals.csv); timestamps
and local machine paths are omitted.

An OpenGL run of the preceding long-menu candidate measured 286 frames versus
199 for the original OpenGL image. It confirms the new indexed path rendered
visibly with OpenGL, but it does **not** qualify the exact final short-menu XBE.
The final Vulkan screenshot was visually checked; no deterministic pixel oracle
or alternate animation/pose/shatter-mode run has been completed.

## Diagnostic attempts

| Candidate | Frames / 10 s | Interpretation |
| --- | ---: | --- |
| Frame-constant sine hoist | 200 | Indexed phase fell about 1 ms; no cadence gain |
| Wave sine lookup | 199 | No useful gain; excluded from final patch |
| Sparse appendage weights alone | 199 | Unique-vertex phase fell about 4 ms; still missed the second VBlank |
| Sparse weights + indexed body, short diagnostic line | 300, 301 | Repeated 30 FPS; diagnostic text changed the UI workload |
| Sparse weights + indexed body, original long menu | 282, 202 | Unstable around the VBlank threshold |
| Sparse weights + indexed body, short menu | 287, 289 | Repeated production-code gain |
| Final full-file image with short menu | 287 | Deliverable image matched the gain |

The generic xemu XISO test suite was not changed or run for this title-side
experiment. Remaining gates for a title release are other dances, pose mode,
shatter controls, and an independent output oracle. No xemu product PR should
claim this title-code improvement as an emulator speedup.
