# MCPX nonstreaming voice regression fixture

## Scope and source separation

This suite drives the guest APU voice engine directly. NXDK's `XAudio`
interface drives AC97 PCM playback and does not exercise MCPX nonstreaming
ADPCM fetching. The fixture needs an output observation after the production
SGE reader, ADPCM decoder, voice resampler and mix stage.

Comparative research used owned xemu register and voice interfaces, NXDK
revision `73c95900965a16be3a3e34b8d4d5d41bc18498be` (MIT), and XboxDev/xboxpy
revision `51ee241f71b2ad708e0f0c5519d5bea538867aaa` (GPL-2.0-or-later) to
understand observable interfaces. This is an OSS-informed independent test,
not a personnel-separated clean room. No driver or decoder source is copied
or translated into this Unlicense repository. The implementation starts from
the behavior and generated-input contract below.

## Generated input and independent oracle

Use 64 blocks of 64 playable samples each. A mono ADPCM block is 36 bytes;
a stereo block is 72 bytes with per-channel four-byte headers followed by
interleaved four-byte channel chunks. The left predictor is +4096, the right
predictor is -4096, both indices and every encoded nibble are zero. At IMA
step index zero the step is 7; nibble zero adds `7 >> 3 = 0` and decreases
the index, which remains clamped at zero. Consequently every decoded sample
equals its channel predictor, including the header sample.

The mathematical unity-gain 24-bit mix values are `0x100000` (left) and
`0xf00000` (right). A declared 32-unit tolerance in signed 24-bit space
allows the voice resampler's floating point arithmetic; it is a narrow
regression observation, not an exact resampler accuracy oracle or proof of
audible quality. Check every sample in both 32-word mix bins and require
observed engine progress plus fresh nonzero output. Silent output, swapped channels and bad routing
must fail. Mono uses +4096 on both output bins. A mono signed-16 PCM case
is the unaffected reader control.

Five leaves: mono aligned, stereo aligned, mono repeated page crossing,
stereo repeated page crossing, and signed-16 mono PCM. Page-crossing cases
start at byte 4080 and loop only the first 64-sample block. Every fetch feeding
the observed mix therefore crosses the scattered-page boundary; later fresh
block predictors cannot hide a corrupted initial fetch. Other leaves loop
4096 samples. All cases hash the full generated input, even when replaying
only its first block. Logical pages map to physical pages 0, 2 and 4 in a
five-page allocation. Pages 1 and 3 contain poison bytes and must stay
unchanged. The regular stereo sequence can also cross a later logical page;
"aligned" means initial block alignment, not whole-sequence single-page
coverage. Hash all generated encoded bytes independently of mix output.

## Guest engine and observation

Use voice 64 in the 2D list, unity sustain, zero pitch, bypass filters,
nonstreaming input, and separate left/right mix bins. Set both observed
bins' submix headroom to zero using their VP methods; voice attenuation
alone does not determine gain when boot headroom remains. The fixture owns
this idle mix configuration and leaves those two headroom values at zero
after cleanup; it does not promise to preserve unknown inactive DSP/mix state.
It restores table addresses and engine/front-end/GP reset registers, keeps
all voice lists empty, and never takes over active work. Keep GP and EP DSP
processors reset, and observe the GP mix-buffer MMIO window written by the
voice stage. Do not load proprietary DSP programs or retail assets.

This register-level setup is initially **xemu-only**. The precise running
SECTL mode and reset/mix-buffer publication behavior have not been qualified
on retail hardware. Record raw mode `0x8` as an experimental xemu setup,
not a newly asserted hardware enum. Full DSP mode is required in the host;
the VP monitor mode clears these mix bins and must fail the output oracle.

Refuse a running engine, either enabled DSP, or nonempty voice lists. Nonzero
table addresses alone do not establish active work: a BIOS can leave them
behind with the engine stopped and all lists empty. Save the prior inactive
engine, front-end, voice/SGE table addresses and GP reset value. The processor
is disabled unless both reset-release bits are set; leave EP unchanged.
After each case, disable the engine and
unlink all voice lists before a GP write obtains the APU frame mutex.
This ordering prevents a frame already waiting in the throttle from
starting a DMA read after the fence. Keep all list tops empty, restore
the saved table addresses and prior inactive engine/front-end/GP values, then
release the fixture allocation. Reset list-top value zero is normalized
to the empty sentinel; running engines and linked application voices are never taken over.
Timeout/failure follows the same cleanup path. If stop verification fails,
retain the small allocation until process reset rather than free a possible
DMA target.

## Timing and qualification

Clear all 64 mix words before arming the engine. Require at least 1024
samples of engine progress from `NV_PAPU_XGSCNT` with a three-second
guest timeout per profile body, then inspect all 64 left/right mix words.
This frame counter avoids short-loop voice-offset aliasing; it does not
claim to count decoded voice fetches. Fresh expected nonzero mix output
is the separate voice-pipeline observation. Setup refusals and allocation/
copy failures emit a failing per-leaf record and `TEST_END` with zero measured
samples and a reason, instead of silently omitting the leaf.
Record bounded guest completion latency and output observations. Progress
polling and host audio pacing mean this is **NOT COMPARABLE as a throughput
benchmark**; there is no fabricated ADPCM speedup from guest wait time.
Use the retained actual-memory component benchmark for isolated reader
cost, and matched native workloads for process resources and game effects.

Host payload/layout known-answer tests, a pinned-NXDK Release XISO build, and
focused original/candidate guest mix checks on Deck are recorded. Independent
framebuffer references, audible/retail coverage, throughput qualification, and
a negative native control for silent or misrouted output remain outstanding.
Publish emulator measurements in the owning xemu PR.

The generated selection is `resources/mcpx-voice-correctness.json`. This
branch adds five leaves to the actual parent catalog of 159 leaves and
five groups: the new catalog has 164 leaves and five groups. Historical
release images with other catalogs are not interchangeable with this build.
