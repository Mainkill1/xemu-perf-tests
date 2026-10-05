# Audio torture workload plan

> **Status: draft / implementation framework.**
>
> This document deliberately separates proven capabilities from planned coverage.
> A test must not advertise an APU code path until the guest workload actually
> drives that path and an oracle or path counter proves that it did.

## Why this exists

Audio is one of xemu's harshest sustained subsystems, but whole-game timing is a
poor first detector for changes inside voice decode, resampling, filtering,
mixing, DMA, DSP, or output scheduling. The audio torture suite is intended to
provide deterministic XISO microbenchmarks that answer two questions before a
full game campaign is started:

1. Did the intended audio code path execute correctly?
2. Did that path get faster or slower for the exact same fixed work?

The normal qualification rule still applies: correctness first, timing second.

## Ground truth and backend split

The public NXDK `XAudio` backend is not a general MCPX voice API. In the pinned
NXDK implementation, `sampleSizeInBits` and `numChannels` are documented as
ignored and the supported payload is currently 16-bit, 2-channel PCM. It feeds
the AC'97 PCM/SPDIF descriptor rings directly.

Therefore an XISO that only calls `XAudioInit` / `XAudioProvideSamples`
**must not claim** that it tested PCM8, PCM24, Xbox ADPCM, mono voices, HRTF,
mixbin fanout, the VP voice engine, GP, or EP.

The suite is split into two explicit backends:

| Backend | Initial status | Legitimate coverage |
| --- | --- | --- |
| `ac97_dma` | workload is implementable, full-suite registration blocked on teardown | 16-bit stereo PCM output, descriptor/ring pressure, refill cadence, callback/interrupt pressure, buffer locality, underrun/drain behavior |
| `mcpx_apu_raw` | framework defined; low-level guest driver required | VP voices, mono/stereo voice formats, PCM8/16/24/32, ADPCM, pitch/resampling, voice modes/control, SGE/SSL fetch, mixbins, filters/envelopes/LFO, 3D/HRTF, GP/EP DSP and related DMA |

The xemu APU model currently defines 256 hardware voices, 64 3D voices, 32
samples per VP frame, 32 mixbins, eight voice-bin selectors, U8/S16/S24/S32
sample-size encodings, an ADPCM container encoding, HRTF state, GP/EP FIFO
registers, and SGE/SSL state. Those definitions are the implementation target,
not permission to mark the coverage complete before the raw guest path exists.

## Test families

The target XISO family is intentionally decomposed. One giant "audio max" test
is useful as a ceiling test but is not a useful first regression detector.

| Family | Purpose |
| --- | --- |
| `audio.ac97_dma` | Establish direct output DMA/refill costs and underrun correctness |
| `audio.vp_scaling` | Scale one controlled voice path from 1 to hardware maximum |
| `audio.format_rate` | Separate source format and source-rate conversion costs |
| `audio.pitch_resample` | Exercise pitch/resampler boundaries and near-Nyquist inputs |
| `audio.buffer_boundary` | Cross 31/32/33-sample and SGE/codec boundaries |
| `audio.streaming_dma` | Stress small refill packets, descriptor churn, and staggered producers |
| `audio.mixbin_fanout` | Route each voice to 1/2/4/8 mixbins and rotate destinations |
| `audio.filter_envelope` | Sweep filter, envelope, and LFO state under fixed voice counts |
| `audio.hrtf_3d` | Exercise up to the supported 3D voice ceiling with deterministic motion |
| `audio.voice_modes` | Isolate stream/buffer, loop, linked, persist, clear-mix, and multipass branches |
| `audio.voice_control` | Isolate lock/reconfigure, on/off, pause/resume, and release methods |
| `audio.voice_churn` | Start/stop/reconfigure voices continuously rather than steady-state only |
| `audio.memory_locality` | Compare shared, contiguous-unique, and page-scattered source storage |
| `audio.gp_ep` | Isolate VP-only, VP->GP, VP->GP->EP, and surround/encode paths |
| `audio.everything_max` | Ceiling test combining expensive legal paths after focused tests pass |

## Voice-count boundaries

The suite must include power-of-two scaling and the boundaries around common
bit-mask/list/worker thresholds:

```text
0, 1, 2, 4, 8, 16,
31, 32, 33,
63, 64, 65,
95, 96,
127, 128, 129,
191, 192, 193,
255, 256
```

A backend may skip values it cannot legally allocate, but it must report the
observed allocation ceiling rather than silently substituting a smaller count.
The raw APU path should also probe `max - 1`, `max`, and `max + 1` so the
failure boundary is tested.

## Format and source-rate matrix

The raw VP backend is expected to cover, where legal:

- PCM U8 mono/stereo
- PCM S16 mono/stereo
- PCM S24 mono/stereo
- PCM S32 mono/stereo
- Xbox ADPCM mono/stereo

Source-rate probes start with:

```text
8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000 Hz
```

The backend should additionally probe the discovered legal minimum and maximum
rate and one adjacent legal value on each side when the programming interface
permits it.

PCM "bitrate" is derived from sample rate, sample width, and channel count; the
suite must not invent a separate bitrate knob for PCM. Codec tests should use
the codec's real block/format semantics.

## Deterministic source signals

Do not ship retail audio. Inputs are generated from fixed integer state and a
stable seed. The source set should include:

- silence
- positive and negative DC
- impulse
- square wave
- deterministic LFSR noise
- low-amplitude noise
- fixed-frequency tones
- multi-tone input
- near-Nyquist input (approximately 0.45 and 0.49 of source rate)

Distinct voices should use non-harmonic identifying tones where practical so a
missing, duplicated, or misrouted voice can be detected spectrally.

## Memory-layout variants

The same logical voice workload must be runnable with at least these source
layouts:

1. `shared`: voices reuse one legal source buffer.
2. `contiguous_unique`: each voice owns a distinct contiguous source.
3. `scattered`: voice data intentionally crosses page/SGE boundaries.

This separates decode/mix work from guest-memory translation and SGE/SSL fetch
cost.

## Buffer and codec boundaries

At minimum, focused cases must exercise buffers at:

```text
31, 32, 33,
63, 64, 65,
127, 128, 129 samples
```

The raw backend must add SGE/page and ADPCM-block cases at boundary - 1,
boundary, and boundary + 1. Loop points and next-segment transitions belong in
this family rather than being hidden inside the maximum-load case.

## Voice mode and control paths

The pinned xemu VP implementation has distinct branches for more than sample
decode and mixing. The focused suite must separately exercise:

- buffer versus stream data type
- loop versus non-loop playback
- linked voices
- persistent voices
- clear-mix behavior
- multipass behavior
- explicit voice lock/reconfigure/unlock
- voice on/off
- pause/resume
- release-envelope transition

These remain separate from `audio.voice_churn`: churn measures repeated state
turnover under pressure, while the mode/control leaves prove that each specific
branch was reached and remained correct.

`NV1BA0_PIO_GET_VOICE_POSITION` is a known gap at the pinned xemu revision:
the method currently enters the unhandled-method assertion. It must therefore
remain a known-gap probe, not a normal fast-gate test, until that xemu path is
implemented.

## AC'97 DMA milestone

An executable AC'97 milestone would be narrower than the final APU suite. It
should use only claims that the NXDK backend can truthfully provide:

- 16-bit stereo PCM
- descriptor/ring occupancy
- refill sizes and cadence
- one producer versus staggered producer scheduling
- shared versus distinct/scattered source buffers
- exact data checksum before submission
- callback/descriptor progress counters
- explicit underrun/drain result

Suggested refill sizes:

```text
32, 64, 128, 256, 512, 2048, 8192 bytes
```

This milestone is valuable on its own because it isolates output DMA and host
audio backpressure while the raw MCPX voice driver is being built.

**Registration blocker:** the pinned NXDK XAudio implementation exposes
`XAudioPause` but no public deinitialization path, and its interrupt object is
private to the implementation. Pausing is not equivalent to restoring the
pre-test device/interrupt state. Do not add AC'97 leaves to the normal full
suite until either (a) a test-owned teardown-capable AC'97 backend exists, or
(b) the runner gives this workload terminal-process/reboot isolation. Running
audio last is useful during development but is not a substitute for a documented
isolation contract.

## Raw MCPX APU milestone

The raw backend must resolve the APU PCI BAR at runtime and program only
documented/validated guest-visible state. Hard-coded xemu host addresses are
not acceptable.

The implementation should be layered:

```text
AudioTortureTests
  |
  +-- deterministic source generator
  +-- workload/case descriptor
  +-- oracle accumulator
  |
  +-- Ac97DmaBackend
  |
  +-- McpxApuBackend
        +-- PCI/MMIO discovery
        +-- SGE/SSL allocator
        +-- voice descriptor builder
        +-- FE method writer
        +-- GP/EP helpers
        +-- teardown/reset
```

The backend must have a real teardown/reset path before it is enabled in the
full suite. Leaving the audio device in a modified state for later unrelated
tests is a suite correctness bug.

## Path-proof contract

Each proposed audio leaf declares the paths it intends to cover; family-level
path lists describe the union of targets, not a claim that every leaf hits
every path. The zero-voice case intentionally declares no VP execution path.
Future xemu
instrumentation should return counters for those paths. A leaf may be timed
without host path counters, but it may not make a path-specific optimization
claim unless the requested counter moved.

Candidate counter names:

```text
apu.frame
apu.vp.voice
apu.vp.decode.pcm8
apu.vp.decode.pcm16
apu.vp.decode.pcm24
apu.vp.decode.pcm32
apu.vp.decode.adpcm
apu.vp.resample
apu.vp.filter
apu.vp.hrtf
apu.vp.mix
apu.vp.sge_read
apu.vp.mode.stream
apu.vp.mode.loop
apu.vp.mode.linked
apu.vp.mode.persist
apu.vp.mode.clear_mix
apu.vp.mode.multipass
apu.vp.control.lock
apu.vp.control.on_off
apu.vp.control.pause
apu.vp.control.release
apu.gp.frame
apu.ep.frame
apu.dma
apu.lock_wait
apu.worker_wait
ac97.descriptor
ac97.irq
ac97.underrun
```

Useful timing/cost fields include:

```text
apu_frame_ns
vp_total_ns
voice_decode_ns
voice_filter_ns
voice_hrtf_ns
voice_mix_ns
sample_fetch_ns
sample_fetch_count
sge_lookup_ns
sge_crossings
mixbin_reduce_ns
gp_ns
ep_ns
dsp_dma_ns
guest_lock_wait_ns
worker_wait_ns
active_voice_count
voice_samples_processed
deadline_misses
```

Normalized results should include cost per voice, per voice-sample, per decoded
byte, per DMA node, and per APU frame where meaningful.

## Correctness versus performance capture

Performance runs must not write PCM/WAV capture inside the timed body.

Use two arms:

- **performance**: audio processing enabled, fixed work, no output-file writes,
  lightweight markers/counters only.
- **correctness**: same workload, capture/analysis allowed, timing ignored.

Correctness analysis may include peak/RMS, DC offset, clipping count, expected
tone amplitude, unexpected tone amplitude, channel leakage, dropout count,
frequency error, and deterministic checksums. Codec paths use codec-appropriate
tolerances instead of byte-identical PCM expectations.

## Fast gate

The normal PR gate should eventually contain a deliberately small but harsh
selection:

1. single-voice PCM16 control
2. maximum PCM16 mono voice scaling
3. maximum stereo voice scaling
4. ADPCM maximum voice scaling
5. 64 3D/HRTF voices
6. maximum mixbin fanout
7. fragmented/SGE-heavy source layout
8. small-packet streaming DMA
9. stream/loop/linked/multipass mode controls
10. lock/on-off/pause/release controls
11. maximum voice churn
12. VP + GP + EP
13. surround/encode path where supported
14. AC'97 descriptor/refill pressure

A regression in one focused leaf is enough to stop before broad game
benchmarking.

## Curated initial case set

The machine-readable matrix expands to **138 planned cases**. This is
deliberately not the full Cartesian product. It fixes the first implementation
targets so another agent cannot quietly reduce or multiply the workload while
claiming the same test semantics.

The initial expansion includes:

- 10 AC'97 DMA/refill/locality cases
- 45 PCM16 mono/stereo VP scaling and allocation-boundary cases
- 29 format/rate cases
- 2 near-Nyquist resampler cases
- 9 31/32/33-style buffer-boundary cases
- 8 streaming/SGE pressure cases
- 4 mixbin fanout cases
- 3 filter/envelope pressure cases
- 4 HRTF/3D scaling cases
- 8 voice-mode cases
- 4 voice-control cases
- 4 voice-churn cases
- 3 source-locality cases
- 4 VP/GP/EP pipeline cases
- 1 all-path ceiling case

Run `python3 utils/audio_torture_cases.py --check` to validate the proposed
case set or `--json` to inspect every fixed parameter set. These are proposed
leaves only; the catalog remains intentionally unchanged until their hardware
backends are real.

## Maximum-load case

`audio.everything_max` is the final ceiling test, not the diagnostic starting
point. It may combine maximum legal voices, mixed formats, mono/stereo, unique
scattered sources, multiple rates/pitches, maximum legal mixbin fanout, 3D/HRTF,
filters, envelopes, LFOs, streaming buffers, continuous parameter updates, GP,
EP, and surround/encode processing.

Its purpose is to answer what fails first under simultaneous pressure. Any
regression found there must be reduced to a focused family before an
optimization is accepted.

## Draft implementation gates

The PR should stay draft until all of the following are true:

- the matrix is machine-readable and host-contract tested
- AC'97 claims are limited to paths the NXDK backend actually drives
- raw APU tests resolve hardware through guest-visible PCI/MMIO
- audio device state is restored after every suite
- every executable leaf has deterministic input and at least one correctness oracle
- catalog IDs and resolved plans are generated, not hand-edited
- focused Release XISO runs complete on xemu
- any path-specific performance claim has matching path proof/counter evidence
- physical-Xbox-safe cases are clearly separated from xemu-only instrumentation
