# PR 55 audio implementation handoff

Updated 2026-10-05. PR #55 remains **open and draft**. Implementation stops here
at the user's request for documentation and Deck cleanup; it is not ready to merge.
The approved scope remains 138 cases in independently selectable family suites,
with `audio.everything_max` an optional, separately selectable ceiling.

## Current coverage

| Family | Matrix cases | Executable | Remaining work |
| --- | ---: | ---: | --- |
| `audio.vp_scaling` | 45 | 45 | Native execution of the other 41 leaves and pinned runner oracles |
| `audio.ac97_dma` | 10 | 0 | Guest-owned descriptors, refill observations, underrun/drain oracles and teardown |
| `audio.format_rate` | 29 | 0 | Format-specific recipes, decode oracles and measured rate consumption |
| `audio.pitch_resample` | 2 | 0 | Near-Nyquist fixtures and frequency/resampling oracles |
| `audio.buffer_boundary` | 9 | 0 | Exact source/SGE/codec boundary recipes and consumption checks |
| `audio.streaming_dma` | 8 | 0 | SSL/SGE producers, refill observations and bounded stop |
| `audio.mixbin_fanout` | 4 | 0 | Independent destination and lane oracles |
| `audio.filter_envelope` | 3 | 0 | Deterministic filter/envelope/LFO state and output oracles |
| `audio.hrtf_3d` | 4 | 0 | Guest-owned HRTF state and deterministic motion/output checks |
| `audio.voice_modes` | 8 | 0 | Distinct mode recipes, branch-specific observations and stop checks |
| `audio.voice_control` | 4 | 0 | Lock, on/off, pause/resume and release state transitions |
| `audio.voice_churn` | 4 | 0 | Bounded start/stop/reconfigure sequences and resource accounting |
| `audio.memory_locality` | 3 | 0 | Shared, unique contiguous and scattered sources with equal output |
| `audio.gp_ep` | 4 | 0 | Owned DSP programs/FIFO/DMA and distinct pipeline oracles |
| `audio.everything_max` | 1 | 0 | Compose only previously proven legal paths; keep optional |
| Total | 138 | 45 | 93 cases still need implementation |

The existing optional nxdk-audio bootstrap is a cross-check, not an implementation
of these remaining families. Default smoke still excludes audio. The public
matrix is in `resources/audio_torture_matrix.json`; do not silently reduce its IDs
or substitute a giant combined test.

## Evidence and qualification limits

The last implementation verification passed 253 host tests and both normal and
optional-audio Release XISO builds. The final targeted Deck comparison selected
only mono zero, mono 256, stereo 256 and the 257th guest-slot allocation refusal.
All four guest leaves passed on both pinned xemu builds, including every cleanup
flag. Active cases observed 256 actual source offsets and eight case frames.
Zero and allocation-denial controls submitted no reference or device work.

| Artifact | Identity |
| --- | --- |
| Guest implementation source | `69eb30e367f584da9f3754608b395753c2e008dd` |
| XISO SHA-256 | `449d36d4ce699690810efbd44c21c629ea023df80f523202e89aae84127547c8` |
| Catalog ID | `sha256:6db2528a4daf04c37a193b77f761b39eeb3b8168332b0cbdd58a06bf3a8d3709` |
| Frozen chunk plan | `sha256:77f24fbc43d9a16f3119c62e4a7115e7cb5681c0e329fd545606143c57eea2e4` |
| Upstream xemu | `ee5ce48b48784f999af374c1452003f8b2b1230f` |
| Upstream executable SHA-256 | `5b6ccf357cfab428e92692b82dc3a5cc75cb50e4065608defbf1cc66b68a597c` |
| Candidate xemu | `c4cdef6cad3dd22d516e16ec2cb1aa9c06ec11f6` |
| Candidate executable SHA-256 | `95f81f33d932cb297d6f637eb0635ac2faa2b895d330bae6871e3012d6353667` |
| Settings | warmup 0, multiplier 1, completion `per_iteration` |
| Upstream run | `20261005-085633811-73f576269693440bbcbe72e27c230c90` |
| Candidate run | `20261005-085722185-03bf09d8dd5f49da895bbae551bd8c44` |

Both runner assessments report execution completed, evidence complete, correctness
failed and comparison ineligible. The exact selection and guest receipt passed;
`xiso_oracle_coverage` failed because all four selected leaves lack pinned runner
oracles. A guest PASS is not permission to self-approve a baseline or claim a
qualified speed improvement. The guest explicitly reports `timing_comparable=false`.

Byte-exact guest receipts and runner assessments were copied and hash-checked
before deleting old Deck runs. See [the evidence index](evidence/pr55-audio-2026-10-05/README.md).
Neither analog sound quality nor end-to-end playback latency has been measured.
Original-Xbox qualification remains withheld because no console is available;
that absence alone does not require expanding this task or inventing hardware proof.

## Source guide

| Area | Files and purpose |
| --- | --- |
| Approved design | [Hardware-compatible design](superpowers/specs/2026-10-04-hardware-compatible-audio-torture-design.md) |
| Completed slices | [Foundation plan](superpowers/plans/2026-10-04-audio-torture-foundation.md), [VP-scaling plan](superpowers/plans/2026-10-05-audio-vp-scaling.md) |
| Fixed case semantics | `utils/audio_torture_cases.py`, `resources/audio_torture_matrix.json`, generated guest descriptors |
| Pure S16 recipes and slot ownership | `src/tests/audio_vp_scaling_recipe.*`, `audio_vp_scaling_source.h`, `audio_voice_slot_pool.h` |
| Admission, DMA, reference phase, polling and teardown | `src/tests/audio_mcpx_raw_backend.cpp`, `audio_apu_ownership.*`, backend/device contracts |
| Output oracle | `src/tests/audio_s16_control_oracle.h` |
| Independently selectable leaves | `src/tests/audio_vp_scaling_tests.*`, `audio_vp_scaling_result.h`, `resources/audio-vp-scaling.json` |
| Catalog and descriptors | `utils/test_catalog.py`, `utils/generate_audio_guest_cases.py` |
| Portable fixtures | `utils/generate_audio_fixtures.py`, compiled fixture contract tests |
| Native failure history | [Audio workload notes](audio-torture-workloads.md#vp-scaling-section-45-selectable-leaves) |

## Implementation rules for the next sections

Implement and register one family at a time. Keep shared admission, allocation and
teardown in the guarded session; use focused family handlers and portable recipes
instead of adding a 138-case switch. Promotion into the executable catalog requires
real submitted work, a case-specific oracle and verified cleanup. Host fakes must
consume the actual generated source and descriptors, not return the expected answer
without using them.

Preserve these findings from native diagnosis:

- Voice handles 0–63 are HRTF-sensitive. Null HRTF handles alone did not make
  routes 0–3 ordinary routes. Scaling uses routes 4/5 for all slots; a 256-voice
  test must not silently mix only the upper 192 voices.
- Submix headroom is write-only. Do not write a guessed default or claim that a
  readback snapshots/restores it. The current session leaves it untouched and
  independently measures a single-voice fixture before the actual case.
- The reference accepts only stable signed output at power-of-two gain divisors
  1–128. This proves count/channel output relative to recorded gain, not absolute
  gain: a uniform gain defect can match another allowed divisor.
- Source length 257 frames avoids a short-loop offset alias. DMA is uncached;
  every submitted voice must show actual current-buffer-offset progress. Reference
  and case phases stop and prove counter quiescence before DMA reuse. Capture mix
  only after stop so the two lanes do not come from different frames.
- Cleanup must prove stop writes, quiet counters, restored readable controls and
  intact DMA guards. Unsafe cleanup poisons audio for the process lifetime and
  retains DMA; do not free memory an active device might still access.
- The 257th refusal is a guest-owned 256-slot pool check, not proof of a hardware
  allocation command. Zero/denial controls perform no DMA allocation or MMIO writes.
- A minor remains: admission/poison failure records report requested counts as
  zero. Their selected case ID and FAIL verdict are correct. Fix this when extending
  failure metadata, without weakening admission or poison handling.

For format/rate work, retain all 29 cases: 5 formats × 2 channel layouts × 2 voice
counts gives 20; the other 9 are S16 mono/64-voice source-rate probes. Constant DC
can check format/count/channel arithmetic but cannot establish rate or pitch.
Add an independent consumption or frequency oracle for those claims.

U8 amplitude 16 quantizes to silence; increasing 256 voices to amplitude 256 can
clip. Use explicit legal route attenuation and calculate its units correctly
(64 attenuation units per dB, not 16). S24 uses the low 24 bits of its 32-bit
container; padding is not audio. S32 uses the full signed word. The portable IMA
ADPCM golden decoder yields 65 frames per 36-byte channel block, while pinned
xemu VP consumption uses 64 with an upstream FIXME. Keep decode truth separate
from hardware-consumption qualification; do not modify the oracle just to agree
with an emulator discrepancy.

AC'97 needs a test-owned teardown-capable backend, not only XAudio calls. DSP and
HRTF need legally distributable, guest-owned state/programs and explicit path
observations. If a register cannot be restored safely, settle session ownership
before registering that case as executable.

## Verification and packaging guide

Run focused portable probes while implementing each family, then the inexpensive
host and generated-file gates. Do not rerun Deck campaigns for documentation edits.

```sh
python3 -m unittest discover -s tests -q
python3 utils/audio_torture_cases.py --check
python3 utils/generate_audio_fixtures.py --check
python3 utils/generate_audio_guest_cases.py --check
python3 utils/test_catalog.py --check
```

The current isolated worktree is `.worktrees/pr55-audio-foundation`, on local
`work/pr55-audio-foundation`, pushed to PR branch `audio-torture-framework`. Preserve
the root workspace's user-owned nxdk changes. Existing build directories are
`bin/build-normal` and `bin/build-audio`; configure normal Release with
`AUDIO_BOOTSTRAP_SMOKE=OFF`, and optional reference Release with it `ON`.
Both use the root checkout's `third_party/nxdk/share/toolchain-nxdk.cmake`.

```sh
cmake --build bin/build-normal -j2
RUSTUP_HOME="$PWD/bin/rustup-local" CARGO_HOME="$PWD/bin/cargo-local" \
  PATH="$PWD/bin/cargo-local/bin:$PATH" cmake --build bin/build-audio -j2
python3 utils/package_runner_suite.py \
  --iso bin/build-normal/src/xiso/xemu-perf-tests_xiso/xemu-perf-tests_xiso.iso \
  --catalog resources/catalog.json \
  --source-commit "$(git rev-parse HEAD)" --output bin/audio-next-suite
```

For a new checkout, configure those build directories before building. Optional
nxdk-audio needs the local newer Rust toolchain (1.90 was installed here); the
normal raw suite does not depend on it. Package only a clean, committed source
that actually produced the image. A documentation-only commit changes Git HEAD
but does not retroactively change the source identity of the retained 69eb30e XISO.

Use Xemu-Test-Runner's `docs/XISO-CAMPAIGNS.md` and `docs/AGENT-API.md` to upload the
new immutable suite/application and select stable IDs; do not launch xemu through
SSH to bypass runner policy. After cleanup the older application/suite registries
are gone: register new definitions rather than assuming historical campaign IDs
still work. Keep one XISO, selection and settings across the upstream/candidate
pair. Start with targeted boundary cases for each new family. Once all 138 cases
exist and independent pinned oracles are approved, perform the agreed full
upstream/candidate comparison and use only targeted reruns for failures.

No xemu modification is required merely to play a tone or execute the current
guest-visible VP checks. These tests observe digital mix/state inside the guest,
not host speaker output. If host audible-quality or end-to-end latency becomes a
separate requirement, design independent PCM capture/timestamp instrumentation
in the runner or xemu and label it as additional evidence, not Xbox ground truth.

## Deck cleanup and restart

The latest retained package is
`/home/deck/xemu-research/workspace/Queue/Tested/agent-xc-pr55-vp-scaling-candidate-69eb30e-01-001`.
Keep its executable, libraries, config, immutable job inputs and EEPROM seed;
`xemu.toml` contains runner-expanded `{runtimeDir}` placeholders and is not a
standalone launch config. The latest results and runtime EEPROM remain under
the candidate run ID above. Its disposable HDD had already been deleted after
evidence collection; the retained dedicated FATX template allows a fresh clone.

Only these four `DiskAssets` are needed for the retained package:

- `pr55-vp-scaling-69eb30e-449d36d4` (XISO)
- `research247-bootrom-e99e3a` (boot ROM)
- `research247-bios-1de4c8` (BIOS)
- `research245-cpu-fatx-compat010-78af83a6` (dedicated FATX template; no backing file)

The installed runner remains at `/home/deck/xemu-research/runner-e17919c` with
`runner.json`. The transient user unit is
`xemu-research-runner-20261003-e17919c.service`. If the unit is still loaded,
restart it with `systemctl --user start xemu-research-runner-20261003-e17919c.service`.
If the transient unit disappeared after logout/reboot, recreate it as deck:

```sh
cd /home/deck/xemu-research
systemd-run --user --unit=xemu-research-runner-20261003-e17919c \
  --working-directory=/home/deck/xemu-research \
  /home/deck/xemu-research/runner-e17919c/XemuTestRunner \
  run -c /home/deck/xemu-research/runner.json --non-interactive
curl --fail http://127.0.0.1:9368/api/v1/status
```

Do not restart it automatically as part of reading this handoff. Cleanup results
will be recorded here after the stopped-state and retained-input checks finish.
