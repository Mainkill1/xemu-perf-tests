# Experimental audible VP fixture

This public test XBE creates one looping stereo PCM voice with independently
generated 480 Hz left and 960 Hz right square waves. It owns only a stopped
APU with disabled GP/EP and empty voice lists. It keeps guest DMA buffers
alive until emulator exit and writes `0x600d` to GP X:$3f1 after voice-engine
sample progress; `0xbad` means the voice did not advance. Progress is not an
audio-output verdict. Two public microprograms also write a sentinel in GP
and EP X:$3f6 when executed; in HLE both must remain zero, while legacy mode
must produce `0x123456` in each. This checks these controlled DSP programs,
not arbitrary microcode. Capture host PCM separately and check each channel's
frequency, amplitude, continuity and cross-talk before calling it audible.
`run_capture.py` creates an owned, temporary Pulse null sink and moves only
audio streams belonging to the emulator process to that sink. It validates
the guest marker and both DSP sentinels, then records five seconds and runs
`analyze_capture.py`. Three consecutive one-second windows must contain the
expected channel frequencies, sufficient signal, no clipping and less than
10% cross-channel fundamental. Silence, swapped channels and short captures
are rejected. Device cleanup and the generated private HDD copy are handled
after each run.

The report also measures whole-process CPU ticks and resident memory over the
fixed post-marker interval. Tick granularity is reported; CPU usage may exceed
100% because xemu uses multiple threads. This fixture is timer-paced and its
CPU numbers do not establish game FPS or effect performance.

For a controlled comparison of the front-channel mix, build the GP-only,
asymmetric-gain variant. Its right voice output has 6 dB attenuation; the
expected right/left fundamental ratio is approximately 0.5. The EP is held
disabled, and the GP program leaves the front mixbins in place for JIT output.
The HLE and JIT captures can therefore be checked against the same PCM input
without attributing effect behavior to either path.

```sh
make NXDK_DIR="$NXDK_DIR" AUDIO_PROOF_ASYMMETRIC=1 AUDIO_PROOF_GP_ONLY=1 -W "$PWD/main.c"
python3 run_capture.py --emulator /path/to/xemu --iso "$PWD/hle-audio-proof.iso" \
  --config /path/to/xemu.toml --output /path/to/new-result \
  --engine 2 --ep-disabled --right-left-ratio .5 --capture-seconds 5
```

Use `--engine 1` in a separate run for the JIT comparison. The runner requires
GP/EP sentinels appropriate to the selected engine and the EP-disabled fixture.
The legacy Default VP monitor intentionally uses a maximum-gain heuristic and
is expected to fail this asymmetric-gain oracle; preserve that negative
control rather than silently accepting identical channels.

This fixture tests a simple PCM voice only. It does not validate DSP effects,
guest-visible DSP state, interrupts, DirectSound APIs, or any real game.
The register setup follows the existing `mcpx_voice` synthetic tests; these
settings need independent Xbox hardware verification before hardware claims.

```sh
export NXDK_DIR=/path/to/built/nxdk
export PATH="$NXDK_DIR/bin:$PATH"
make NXDK_DIR="$NXDK_DIR" -W "$PWD/main.c"
```
