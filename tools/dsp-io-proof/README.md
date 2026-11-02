# Public DSP XISO and isolated native arithmetic proof

This independently authored nxdk disc executes three GP DSP Q23 gain routes
(+1/2, -1/2, +1/4), 64 inputs each. The guest validates all 192 outputs in DSP
X memory and a 768-byte scratch DMA transfer, input preservation, and publishes
a verdict. The host pauses the owned emulator and independently validates
the full program image, all inputs, all 192 DSP and 192 DMA output words via
QMP. The portable C native worker computes the same three arithmetic routes
in an isolated process and compares them with the admitted guest report.

This proves an arithmetic HLE development boundary. It does not install a
live APU dispatcher or qualify scheduling, register transitions, persistent
state, fallback or game filters. xemu PRs #379/#380 remain separate game-filter
work. This standalone tool is separate from the main test-suite catalog.

## Build

Use a built nxdk checkout; committed `program.h` permits rebuilding without
an assembler. Use Python 3.11+ for the host tools.

```sh
export NXDK_DIR=/path/to/nxdk
export PATH="$NXDK_DIR/bin:$PATH"
cd tools/dsp-io-proof
make NXDK_DIR="$NXDK_DIR" -W "$PWD/main.c"
cc -std=c11 -O2 -Wall -Wextra -Werror native_gain.c -o native_gain
python3 test_native.py
```

When changing DSP code, regenerate with `python3 generate_program.py
--assembler /path/to/dsp56300-asm --output program.h`. The tested assembler is
dsp56300-asm 1.0.0 at xemu-project/dsp56300 commit
`b36db2c23ee2dd6e643f48e4dc6288074030e1a0`. It encodes independently authored
assembly; no game microcode or upstream test program is copied. The 1239-word
program bootstraps through two RAM SGE pages. Its full zero-padded 4096-word
little-endian SHA-256 is
`41a14ad0eff5ce00e45fb73c81f497d1d1056bf1ffc6301b91b1d78d5663778a`.

## Run and compare native outputs

Use normal legal firmware, a graphical Linux session and full-DSP/JIT xemu.
The runner makes private copies of firmware, EEPROM and HDD. Source settings
and writable images are not modified. Choose a new output directory each time.

```sh
python3 run_guest.py --emulator /path/to/xemu \
  --iso "$PWD/dsp-io-proof.iso" --program-header "$PWD/program.h" \
  --config /path/to/xemu.toml --output /path/to/new-owned-result
python3 compare_native.py --guest-report /path/to/new-owned-result/report.json \
  --worker "$PWD/native_gain"
```

For a launcher wrapping an ELF, add `--emulator-binary /path/to/ELF`. Reports
identify both binaries, the ISO/program and all compared words. Private images
and logs stay under the private subdirectory. Keep raw evidence with the
owning emulator PR instead of source commits. The mailbox is GP X:$3f0..$3f5:
completion $51d00d, verdict $600d/$bad, poll count, failure count and low-24 /
high-8 DMA pointer. Scratch/SGE buffers stay allocated until process exit.
Physical-Xbox execution is unqualified; this is an xemu fixture.

## Capture then replay 100 times

Use xemu PR #384's tools plus the exact GP program trigger. `--capture` creates
the expected full P image and sets `XEMU_DSP_CAPTURE_GP_PROGRAM`; the recorder
waits for that enabled program before recording one frame. A first-N recorder
alone can select an empty BIOS frame, rejected as `no physical context`.

```sh
python3 run_guest.py --emulator /path/to/capture-enabled-xemu \
  --iso "$PWD/dsp-io-proof.iso" --program-header "$PWD/program.h" \
  --config /path/to/xemu.toml --output /path/to/new-capture-result --capture
python3 replay_capture.py --tools /path/to/xemu/tests/xbox/mcpx-apu \
  --worker /path/to/xemu/build/dsp-replay-worker \
  --capture /path/to/new-capture-result/capture.xcr \
  --output /path/to/new-replay-inputs --repeat 100
```

Reconstruction retains INCOMPLETE authority for unobserved RAM/provenance.
Repeated replay can establish BASELINE_MATCH for the modeled input; it does
not silently seal an authoritative corpus.

## Concurrent DSP/native shadow

An emulator with the experimental gain shadow worker can compare the three
routes during the real XISO frame. The emulated DSP remains authoritative;
native code executes on a separate precreated worker with copied inputs.

```sh
python3 run_guest.py --emulator /path/to/shadow-xemu \
  --iso "$PWD/dsp-io-proof.iso" --program-header "$PWD/program.h" \
  --config /path/to/xemu.toml --output /path/to/new-shadow-result --shadow
```

`--shadow-routes 5` runs half/quarter natively and counts inverted-half as
LLE-only fallback. `--shadow-routes 0` must report NO_COMPARISONS, not success.
`--shadow-fault 65` deliberately corrupts inverted-half sample 1: the original
guest checks must still pass while the shadow campaign reports MISMATCH and
returns nonzero. Stats include native/fallback calls, compared/matching/
different words, first difference and diagnostic native wall time per route.
The host independently validates counter consistency. `guest_status` retains
the original guest verdict when a shadow candidate fails. The host uses the
final paused, idle APU snapshot after allowing normal shutdown to finish;
all snapshots are validated and their counters must never decrease.
An enabled fault on a selected route must cause a mismatch in every admitted
job; merely reporting the configured fault index cannot pass the control.
The runner clears inherited shadow enable/mask/fault settings before applying
its command-line options, so an off control cannot silently inherit shadow work.

## Negative controls

```sh
make NXDK_DIR="$NXDK_DIR" SRCS="$PWD/negative.c" \
  OUTPUT_DIR=negative-bin GEN_XISO=dsp-negative.iso -W "$PWD/negative.c"
python3 run_guest.py --emulator /path/to/xemu \
  --iso "$PWD/dsp-negative.iso" --program-header "$PWD/program.h" \
  --config /path/to/xemu.toml --output /path/to/new-negative-result
python3 compare_native.py --guest-report /path/to/new-owned-result/report.json \
  --worker "$PWD/native_gain" --inject-fault
```

The negative guest changes an expected word and must return FAIL even when
actual DSP/DMA output agrees. Injected native corruption must return MISMATCH
at route 0/sample 0. Both exit nonzero. `-W` forces the correct nxdk variant
when switching between positive and negative builds sharing `main.exe`.

## Limits

Dummy audio, completion polling and boot duration are NOT COMPARABLE
throughput. No game, audio-device or hardware-accuracy improvement is claimed.
An interpreter Deck attempt timed out; it is not a passing platform result.
Live HLE still requires exact recognition, staged effects, persistent-state /
fallback validation, native coverage and matched XISO/game/resource evidence.
