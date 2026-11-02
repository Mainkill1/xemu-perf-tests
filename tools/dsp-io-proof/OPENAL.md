# OpenAL Soft loopback candidate probe

`openal_loopback_probe.py` evaluates the public DSP gain fixture through the
installed OpenAL Soft library. It is a standalone Python/ctypes experiment;
it does not link a new audio backend into xemu or serve live guest audio.

```sh
python3 openal_loopback_probe.py --guest-report /path/to/result/report.json
python3 test_openal_loopback.py
```

Use a passing `run_guest.py` report with its verified full program identity,
64 input words and 192 DSP output words. `--library` optionally selects the
library explicitly. Missing extensions or unsupported formats return nonzero
with UNSUPPORTED; invalid inputs and setup failures cannot pass. The unit
tests separately report a skip if the installed library lacks the required
extensions. Unit fixture identities are not native XISO evidence.

Each route uses a fresh loopback device/context, 48 kHz stereo float32 input
and output, direct channels, disabled output limiter and HRTF where available.
The probe checks the requested device format and limiter/HRTF state. Left
channel Q23 samples enter OpenAL at the same sample rate; the right channel
is zero and checked for cross-talk. Gains are +1/2, -1/2 and +1/4. Because
OpenAL gain is nonnegative, the negative route explicitly negates its input
before applying gain 1/2. Float output is floored back to signed Q23 and
compared word-for-word with the emulated DSP. This wrapper arithmetic is
part of the candidate, not evidence of negative OpenAL gain support.

The report records each route's compared words, mismatches, first differing
sample, right-channel leakage and diagnostic render-call wall time, plus
OpenAL vendor/version/renderer and the loaded library hash on Linux. These
single calls have neither balanced timing repetitions nor equivalent DSP
work scopes: `timing_comparable` is false. They establish no speedup.

The tests include signed extremes, negative rounding and a deliberately
altered expected output; the latter must report exactly one difference.
No audio playback device is opened. The null backend environment is set
before library loading to avoid initializing a real system audio backend.

## Fit for gradual HLE

Loopback gives the emulator control over the number of samples rendered and
lets a future candidate return a private output buffer for shadow comparison.
Keep DSP execution authoritative while testing individual routes. Retain LLE
for unknown programs or unsupported state. Serving native audio would require
its own qualified dispatch, state transfer and fallback implementation.

This gain probe says nothing about Xbox effect coefficients, resampling,
reverb history, fixed-point saturation/rounding in other operations, DSP
registers, interrupts, DMA/FIFO effects, reset, save/load, or resource/performance
regressions. OpenAL's generic API does not define arbitrary MCPX microcode
semantics. Those contracts must be established independently before routing
game DSP work through it. The current xemu SDL playback path is unchanged.

Public specifications used for this independently written probe:

- [ALC_SOFT_loopback](https://openal-soft.org/openal-extensions/SOFT_loopback.txt)
- [ALC_SOFT_output_limiter](https://openal-soft.org/openal-extensions/SOFT_output_limiter.txt)
- [ALC_SOFT_HRTF](https://openal-soft.org/openal-extensions/SOFT_HRTF.txt)
- [AL_SOFT_source_resampler](https://openal-soft.org/openal-extensions/SOFT_source_resampler.txt): algorithms are implementation-defined.
- [OpenAL headers and public constants](https://github.com/kcat/openal-soft/blob/master/include/AL/al.h)

The probe contains no copied mixer, resampler or effects implementation.
