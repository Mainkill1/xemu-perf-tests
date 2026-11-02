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

This fixture tests a simple PCM voice only. It does not validate DSP effects,
guest-visible DSP state, interrupts, DirectSound APIs, or any real game.
The register setup follows the existing `mcpx_voice` synthetic tests; these
settings need independent Xbox hardware verification before hardware claims.

```sh
export NXDK_DIR=/path/to/built/nxdk
export PATH="$NXDK_DIR/bin:$PATH"
make NXDK_DIR="$NXDK_DIR" -W "$PWD/main.c"
```
