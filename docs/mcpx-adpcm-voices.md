# MCPX nonstreaming voice regression fixture

## Scope and source separation

This planned suite drives the guest APU voice engine directly. NXDK's `XAudio`
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
observed voice progress. Silent output, swapped channels and bad routing
must fail. Mono uses +4096 on both output bins. A mono signed-16 PCM case
is the unaffected reader control.

Five leaves: mono aligned, stereo aligned, mono initial page crossing,
stereo initial page crossing, and signed-16 mono PCM. Page-crossing cases
start at byte 4080. Logical pages map to physical pages 0, 2 and 4 in a
five-page allocation. Pages 1 and 3 contain poison bytes and must stay
unchanged. The regular stereo sequence can also cross a later logical page;
"aligned" means initial block alignment, not whole-sequence single-page
coverage. Hash all generated encoded bytes independently of mix output.

## Guest engine and observation

Use voice 64 in the 2D list, unity sustain, zero pitch, bypass filters,
nonstreaming input, and separate left/right mix bins. Keep GP and EP DSP
processors reset, and observe the GP mix-buffer MMIO window written by the
voice stage. Do not load proprietary DSP programs or retail assets.

This register-level setup is initially **xemu-only**. The precise running
SECTL mode and reset/mix-buffer publication behavior have not been qualified
on retail hardware. Record raw mode `0x8` as an experimental xemu setup,
not a newly asserted hardware enum. Full DSP mode is required in the host;
the VP monitor mode clears these mix bins and must fail the output oracle.

Refuse to replace a running voice engine. Save the prior engine/list/table
and DSP-reset register values. After each case, disable the engine and
unlink all voice lists before a GP write obtains the APU frame mutex.
This ordering prevents a frame already waiting in the throttle from
starting a DMA read after the fence. Restore inactive prior state only
after quiescence, then release the fixture allocation. Timeout/failure
must follow the same cleanup path.

## Timing and qualification

Record bounded guest completion latency and output observations. Progress
polling and host audio pacing mean this is **NOT COMPARABLE as a throughput
benchmark**; there is no fabricated ADPCM speedup from guest wait time.
Use the retained actual-memory component benchmark for isolated reader
cost, and matched native workloads for process resources and game effects.

Qualification requires host payload/layout known-answer tests, pinned-NXDK
Release XISO build, original/candidate runs through the maintained HTTP
runner on Deck `10.0.0.123`, captured output assertions, a negative control
for silent/misrouted output, and safe cleanup verification. Keep a genuine
test-suite PR draft until these gates are complete. Publish emulator
measurements in the owning xemu PR.
