# Audio torture workload plan

> **Status: draft / 45 executable VP-scaling leaves, 93 cases still planned.**
>
> Four boundary leaves have targeted guest PASS evidence on both pinned xemu
> builds; the full family is not natively qualified. See the
> [PR #55 handoff](pr55-audio-handoff.md) for current coverage and next steps.
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
| `mcpx_apu_raw` | 45 S16 mono/stereo scaling leaves implemented; non-scaling cases remain planned | Current: S16 static VP count/channel correctness. Target: other formats, rates, modes/control, SGE/SSL, mixbins, filters/envelopes/LFO, HRTF and DSP |
| `nxaudio_reference` | optional bootstrap backend implemented; execution validation pending | full MCPX/GP/AC97 initialization and teardown plus static U8/S16/S24/S32/ADPCM reference voices |

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

## Checked-in audio fixtures

The XISO carries 10 deterministic fixtures under `resources/audio/` (10,358
bytes total): three audible PCM16 WAV files, raw S16/S24-in-B32/S32 samples,
mono/stereo Xbox ADPCM blocks, and decoded ADPCM S16 goldens. They are generated
by `utils/generate_audio_fixtures.py`, contain no third-party recordings, and
are covered by the repository's Unlicense dedication.

Every checked-in fixture has a size, SHA-256, and FNV-1a64 value in
`resources/audio/manifest.json`; CI regenerates the set byte-for-byte. U8 is
generated deterministically at runtime from the integer S16 signal source.
MIDI remains out of scope for this phase because it primarily adds a
sequencer/synth software path before PCM reaches MCPX.

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

## Safe discovery and reference bootstrap

`McpxApuDevice::ProbeAndMap()` remains read-only: it scans PCI bus 0 for
`10de:01b0`, validates/maps BAR0, and snapshots key APU registers.
`McpxApuDevice::Open()` admits only a stopped, empty-list cold state or the
exact quiescent firmware profile observed on the Deck, including a quiet sample
counter across a 3 ms interval. Its narrow register-write allowlist becomes
available only after admission. `ProbeAudioInfrastructure()` combines read-only
discovery with fixture checksum validation.

For an end-to-end development smoke, build with
`-DAUDIO_BOOTSTRAP_SMOKE=ON`. That opt-in build pins
Ryzee119/nxdk-audio at `fc2deca2cc1e434805ac03ca7c2f500b3b028f36` (MIT),
runs the read-only discovery probe, submits one 48 kHz S16 mono static voice,
waits for completion, destroys the voice, and calls `nxAudioShutdown()`.
The switch defaults OFF and the smoke is not catalog coverage.

A dedicated CI job builds this bootstrap XISO separately so normal qualification
builds do not acquire the Cargo/DSP-assembler dependency.

## Raw MCPX APU milestone

The raw backend resolves the APU PCI BAR at runtime and programs only
documented/validated guest-visible state. Hard-coded xemu host addresses are
not acceptable.

The implementation should be layered:

```text
15 catalog families with independently selectable suites
  +-- AudioVpScalingTests (45 individually selectable leaves)
  +-- other family suites (planned)
  |
  +-- shared typed 138-case descriptor and deterministic fixtures
  +-- guarded raw MCPX and future test-owned AC'97 backends
  +-- family-specific output/state oracles and teardown
```

The backend must have a real teardown/reset path before it is enabled in the
full suite. Leaving the audio device in a modified state for later unrelated
tests is a suite correctness bug.

### Historical first VP-scaling leaf: Deck evidence, 2026-10-05 UTC

Historical Deck artifact URLs below were retired during the requested cleanup
on 2026-10-05. Only the latest candidate package/run remains on the device.
The final paired boundary receipts are preserved byte-exact in
[the repository evidence directory](evidence/pr55-audio-2026-10-05/README.md).

At this foundation checkpoint only `audio.vp_scaling.s16_mono.v001` was executable
in the new hardware-safe family catalog. The other 137 matrix cases were planned; this leaf was
correctness-only, opt-in for current Deck development, and excluded from the
default smoke plan. Its guest oracle requires observed engine progress, all
32 stopped-frame GP mix samples to match a fixed nonzero S16 control level
within 32 S16 levels of fixed-point error, and verified stop, register
restoration, quiet counter, and DMA guard before memory release.

The exact normal XISO was built from source commit
`29185f2054771802a2bd8018895d42bcc142cb0c`, SHA-256
`deca474cf431e20e66dcc3f8868516928dda45f00ff4fb0a28464136a0fa499c`.
Its catalog ID is
`sha256:cdc52c104b4d48d5a86d644a16de7e0ae69a71159a8c11d2b31c19989eb24193`
and catalog-file SHA-256 is
`f0b4b51a2167c117ace9c2d402609019ed07721c2e568e3b91fae72bd45b4e23`.
Both campaigns selected this leaf alone with zero warmups, multiplier 1,
per-iteration GPU completion, the same configuration SHA-256
`0318e8887b2144ba6a5cb6536df14b04b80eadf8a21debb242f4e80904034dce`,
and the same resolved chunk plan
`sha256:31d0ea61d406bb3801215651872f1061f4a849cc9bd75d7314472ec65598acbc`.

| Deck executable | Exact executable SHA-256 | Observed guest result |
| --- | --- | --- |
| Upstream xemu `ee5ce48b48784f999af374c1452003f8b2b1230f` | `5b6ccf357cfab428e92692b82dc3a5cc75cb50e4065608defbf1cc66b68a597c` | [Run `20261005-071324531-f9499e62b4fb417c8c5c730c3fa036ba`](http://10.0.0.123:9368/api/v1/runs/20261005-071324531-f9499e62b4fb417c8c5c730c3fa036ba/artifacts/guest/results.txt): guest `PASS`, 19 observed engine frames, output and teardown pass |
| Candidate xemu `c4cdef6cad3dd22d516e16ec2cb1aa9c06ec11f6` | `95f81f33d932cb297d6f637eb0635ac2faa2b895d330bae6871e3012d6353667` | [Run `20261005-071414774-abe49da94d904d298218103da8a4ac7d`](http://10.0.0.123:9368/api/v1/runs/20261005-071414774-abe49da94d904d298218103da8a4ac7d/artifacts/guest/results.txt): guest `PASS`, 13 observed engine frames, output and teardown pass |

These are complete selected-leaf guest receipts, **not** runner-qualified
baseline or performance comparisons. The runner API v1 reports the new leaf
has no pinned runner-side reference oracle, so both unpaired campaigns have
`xiso_oracle_coverage=false` and an overall failed/ineligible assessment even
though each guest leaf passed. Runner binary version was not exposed by the
queried service endpoints. No original Xbox was available; hardware
qualification remains withheld. Do not promote this PR or the other 137 cases
from these two runs.

The captures above are historical triangle-source evidence. Two later targeted
runs at `4e04027` passed teardown but failed that oracle because a filtered,
fractionally shifted triangle window does not reliably match integer source
samples. That oracle was replaced with a fixed S16 +4096 control input for the
scaling leaf; changing-waveform resampling requires its own family oracle.

The final single-voice foundation source commit was
`cef52da71fbbbc0820600b1ef3fa791cc1963231`, with normal-XISO SHA-256
`370f38401c666e76e201fc01544060d588e090fb7abc029d336d84caefff1a2b`.
Catalog/configuration identities and effective settings remain those listed
above; the new resolved chunk plan is
`sha256:4cabf57913464d645e624e117589b1c9ce699e87a49bd6cc1bff29edf4f74d55`.
It includes restore-write/readback checks for every modified control
and a process-lifetime audio lockout after unsafe teardown. Host fault
injection checks failed writes, ineffective restore writes, retained DMA, and
subsequent-case rejection; all 251 host tests and both Release XISO builds pass.

| Current exact image | Retained guest result |
| --- | --- |
| Upstream | [Run `20261005-080026986-8ce5e2444fa8421dbbc4d4ad6625548e`](http://10.0.0.123:9368/api/v1/runs/20261005-080026986-8ce5e2444fa8421dbbc4d4ad6625548e/artifacts/guest/results.txt): `PASS`, 14 engine frames, all 32 mix words `1048577`, every cleanup check passes |
| Candidate | [Run `20261005-080119187-ff2cf36b52b44108b66f088914dd0bef`](http://10.0.0.123:9368/api/v1/runs/20261005-080119187-ff2cf36b52b44108b66f088914dd0bef/artifacts/guest/results.txt): `PASS`, 14 engine frames, all 32 mix words `1048577`, every cleanup check passes |

The expected mix level is `1048576`; tolerance remains 32 S16 levels. These
receipts still have missing runner-side oracle coverage and do not establish
timing eligibility, analog fidelity, or original-Xbox qualification.

### VP-scaling section: 45 selectable leaves

All 45 `audio.vp_scaling` cases now have independent routes in
`AudioVpScalingTests`; `resources/audio-vp-scaling.json` selects only this
section. The remaining 93 audio descriptors stay planned. PR #55 stays draft.
The normal and optional-audio Release images build, and all 253 host checks pass.

Active cases use a 257-frame source, amplitude `4096 / voice_count`, positive
mono/left and negative stereo right. Every submitted voice must advance its
uncached source offset, and the engine must advance at least eight frames.
Slots 64..255 use ordinary routes 0/1; slots 0..63 use ordinary routes 4/5,
with HRTF-specific routes muted and null HRTF handles. This avoids depending
on write-only global HRTF routing and headroom settings.

Submix headroom methods also lack a readable prior value. The session leaves
them untouched. Each active case first observes an independent one-voice S16
4096 reference, accepting only stable signed output with a gain divisor that
is a power of two from 1 through 128. It then stops and proves counter quiescence
before reusing DMA for the requested count. The case oracle checks its actual
mix against the independently inferred divisor, with tight scaled tolerance.
The reference samples, observed progress, divisor, and source checksum are
recorded separately. This proves count/channel correctness relative to a
recorded fixture gain, not absolute analog gain; a uniform gain defect could
match a different allowed divisor. Zero/denial controls submit neither a
reference nor case work and preserve device/mix state.

Two diagnostic revisions were retained before the final targeted pass.
At `82303cc`, all 256 voice offsets advanced, but output matched only 192
contributing voices because the lower slots' first four routes were overridden.
At `1c3e83c`, corrected routing and preserved firmware headroom produced a
half-scale mix, demonstrating why a unity assumption was invalid. These are
attributed guest-setup/oracle failures, not candidate-only emulator regressions.

The validated source is `69eb30e367f584da9f3754608b395753c2e008dd`.
Normal-XISO SHA-256:
`449d36d4ce699690810efbd44c21c629ea023df80f523202e89aae84127547c8`.
Catalog ID:
`sha256:6db2528a4daf04c37a193b77f761b39eeb3b8168332b0cbdd58a06bf3a8d3709`;
catalog-file SHA-256:
`e928773511a16155e1693f6b952e90954fab86bbdcc90d323696fc7de8bb6a96`.
Both runs use the pinned upstream/candidate executables listed above,
configuration SHA-256 `0318e8887b2144ba6a5cb6536df14b04b80eadf8a21debb242f4e80904034dce`,
warmup 0, multiplier 1, per-iteration completion, and resolved plan
`sha256:77f24fbc43d9a16f3119c62e4a7115e7cb5681c0e329fd545606143c57eea2e4`.

| Exact run (receipts retained in this repository) | Selected guest results |
| --- | --- |
| [Upstream `20261005-085633811-73f576269693440bbcbe72e27c230c90`](evidence/pr55-audio-2026-10-05/upstream-results.txt) | All four PASS; mono/stereo 256 observe 256 voices and 8 case frames; reference frames 14/10 |
| [Candidate `20261005-085722185-03bf09d8dd5f49da895bbae551bd8c44`](evidence/pr55-audio-2026-10-05/candidate-results.txt) | All four PASS; mono/stereo 256 observe 256 voices and 8 case frames; reference frames 11/10 |

The four selections are mono zero, mono 256, stereo 256, and the 257-slot denial.
Each active reference infers divisor 2 in both lanes. Mono case mix is
`524288` in both lanes; stereo case mix is `524288` left and `16252928`
(signed 24-bit `-524288`) right. The denial accepts 256 guest-pool slots and
refuses exactly one, while observing/submitting no device voices. All teardown
flags pass in all eight selected receipts. Runner receipt matching and exact
four-leaf coverage pass, but pinned oracles for these selections remain absent:
`xiso_oracle_coverage=false`, overall failed/ineligible. Only these four leaves
were run natively in this partition, not all 45. Full 138-case comparison,
runner qualification, original-Xbox execution and timing claims remain withheld.

Independent review caught the low-slot routing issue and the inherited
write-only headroom mutation; regression tests cover both corrections. A
minor diagnostic gap remains: admission/poison failures report requested count
zero, while retaining the correct selected case ID and a FAIL verdict.

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

The machine-readable matrix expands to **138 cases: 45 executable and 93 planned**. This is
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
case set or `--json` to inspect every fixed parameter set. Only the 45 VP-scaling
leaves are promoted into the executable catalog. Other families remain planned
until their hardware backends, per-case oracles and teardown exist.

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
