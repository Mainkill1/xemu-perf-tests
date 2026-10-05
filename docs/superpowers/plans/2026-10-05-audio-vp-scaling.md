# Audio VP Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. The user has approved direct implementation and continued work on draft PR #55.

**Goal:** Implement all 45 individually selectable VP-scaling cases, including mono/stereo counts from zero to 256 and an explicit 257-slot denial.

**Architecture:** A focused S16 source/voice recipe feeds the guarded raw session. The scaling suite registers each descriptor as its own leaf; zero and allocation-denial controls submit no device work. Future format, mode, DSP and AC'97 families remain separate handlers and suites.

**Tech Stack:** C++17/NXDK, Python host contracts, normal and optional-audio Release XISOs, Deck runner API.

**Spec:** `docs/superpowers/specs/2026-10-04-hardware-compatible-audio-torture-design.md`

**Status 2026-10-05:** All four tasks in this 45-case slice are complete, including
targeted paired Deck evidence at `69eb30e`. This does not complete the 138-case PR.
See [the handoff](../../pr55-audio-handoff.md) for the remaining 93 cases,
qualification limits and stopped-runner restart instructions. Task checklists
below describe the original execution sequence, not newly requested reruns.

## Global Constraints

- Keep PR #55 draft until all 138 cases pass the full agreed gate.
- Use guest-visible PCI/BAR/MMIO and no emulator-private command.
- A PASS requires observed progress, a case-specific output/state oracle, and verified teardown.
- Retain DMA and block later audio work after unsafe cleanup.
- Preserve the user-owned `third_party/nxdk` checkout.
- Withhold original-Xbox and analog-output qualification.
- Retain the 138 matrix IDs and all specified channel/voice counts.
- Keep each case independently selectable and the ceiling optional.

## Files and Responsibilities

- `audio_vp_scaling_recipe.h/.cpp`: validate static scaling requests and build source/linked voice descriptors.
- `audio_voice_slot_pool.h`: bounded 256-slot guest resource ownership and explicit denial.
- `audio_s16_control_oracle.h`: constant amplitude/channel/count oracle.
- `audio_mcpx_raw_backend.cpp`: admitted session, DMA, actual per-voice observation, and teardown.
- `audio_vp_scaling_tests.cpp` and result header: family leaf registration and truthful result emission.
- Guest/catalog generators: only promote the 45 completed scaling IDs.

## Review Focus

1. Slots below 64 must explicitly bypass HRTF; a 256-voice 2D case must not silently acquire 3D filtering.
2. Short repeating sources can alias CBO to zero; use a 257-frame control and require observed CBO change for every submitted voice.
3. Stereo channels must remain distinguishable; left is positive and right negative.
4. Zero/denial controls must preserve mix/control state without DMA allocations or MMIO writes.
5. Failed setup and poisoned sessions must still emit one selected leaf record.

### Task 1: Build the scaling recipe and portable oracle

**Files:** Create `src/tests/audio_vp_scaling_recipe.h/.cpp`, `src/tests/audio_voice_slot_pool.h`, `tests/audio_vp_scaling_recipe_probe.cpp`, `tests/test_audio_vp_scaling_recipe.py`; modify `audio_vp_scaling_source.h`, `audio_s16_control_oracle.h`, and CMake sources.

**Interfaces:** `bool BuildS16ScalingSource(const WorkloadSpec &, std::vector<uint8_t> &, std::string &)`. The source contains 257 frames at signed amplitude `4096 / voice_count`, positive left/mono and negative right. `uint16_t ScalingVoiceHandle(uint32_t ordinal)` visits 64..255 then 0..63. `bool PrepareS16ScalingVoiceTable(const WorkloadSpec &, uint8_t *, size_t, uint32_t source_frames, std::string &)` writes a 256-slot table with exact linked list, S16/container/stereo fields, loop, unity gains, and null HRTF handles. `VoiceSlotPool::Allocate(uint16_t &)` returns false after exactly 256 distinct handles. Extend `S16ControlObservation` with requested/observed voice counts, channels, and right mix words.

- [x] Write a compiled probe asserting source lengths 514/1028, count-2 amplitude +2048/-2048, count-256 amplitude 16, exact 256 unique handles and 257th denial, link termination, null HRTF, and per-channel oracle failure for silence, swapped channels, wrong count, missing progress, or wrong output.
- [x] Run `python3 -m unittest tests.test_audio_vp_scaling_recipe -v`; expect failure on missing interfaces.
- [x] Implement the pure recipe/pool/oracle with bounded validation. Reject counts >256 and channels outside 1/2. No Xbox headers in these units.
- [x] Run the focused probe and existing raw S16 tests; expect PASS.
- [x] Commit `Build S16 voice scaling recipes and observed amplitude oracle`.

### Task 2: Execute all scaling requests through one guarded session

**Files:** Modify `audio_mcpx_raw_backend.cpp`, `audio_torture_backend.h`; create `tests/audio_vp_scaling_backend_probe.cpp`, `tests/test_audio_vp_scaling_backend.py`; adapt the existing one-voice lifecycle probe.

**Interfaces:** Retain `McpxRawBackend::Run(const AudioCaseDescriptor &, WorkloadResult &, std::string &)`. Extend results with requested/accepted/refused/observed voice counts and `resource_control_passed`. Shared-source S16 DMA fits one page; voice-table/SGE allocations keep guards. Read uncached voice CBO through volatile memory while polling engine progress; require every requested voice to change offset. Record counts only from that observation.

- [x] Add a fake device that resolves actual allocated voice/SGE/source memory, advances per-voice offsets, and mixes the configured channels. Assert all 45 descriptors execute; a skipped voice fails; stereo reversal fails; zero and 257 controls perform no writes/allocations and preserve state; cleanup failure poisons a newly constructed backend.
- [x] Run `python3 -m unittest tests.test_audio_vp_scaling_backend -v`; expect failure because the backend accepts only the original leaf.
- [x] Generalize only the static scaling family. For normal cases require 256 engine samples and observed progress on every linked voice within 3 seconds. For zero and 257 controls compare pre/post mix and ownership without submitting work. Validate the denial descriptor's exact request 257/accepted256/refused1. Preserve complete restore readback and retained DMA policy.
- [x] Run all host tests and both Release builds; expect PASS. A host PASS is not native qualification.
- [x] Commit `Execute bounded mono and stereo VP voice scaling cases`.

### Task 3: Register 45 individual family leaves

**Files:** Modify `audio_vp_scaling_tests.h/.cpp`, `audio_vp_scaling_result.h`, `utils/generate_audio_guest_cases.py`, `utils/test_catalog.py`, related catalog/leaf contract probes; regenerate the guest include and resource catalog/plans.

**Interfaces:** `AudioVpScalingTests::RunCase(const AudioCaseDescriptor &, const std::string &legacy_name)` emits one result. Legacy names are `S16MonoV000`/`S16StereoV000` through matrix counts, plus `S16MonoAllocationV257`. Preserve the existing stable IDs and first leaf name. Promote exactly the scaling family, leaving 93 other matrix cases planned.

- [x] Update contract tests to require exactly 45 scaling leaves/descriptors, exact per-leaf route names, unique selection, boundary correctness metadata, failure records, no default-smoke promotion, and no non-scaling executable descriptors.
- [x] Run the affected catalog/descriptor/leaf tests; expect RED with only one existing leaf.
- [x] Implement thin family registration from typed descriptors and generalized metadata with resource/observed counts. Generator names match the C++ routes. Add `resources/audio-vp-scaling.json` selecting the 45 cases explicitly.
- [x] Run descriptor, catalog, plan, runner-package checks, full host tests, and both Release builds; expect PASS.
- [x] Commit `Expose all 45 focused VP scaling leaves`.

### Task 4: Targeted Deck proof and evidence

**Files:** Modify `docs/audio-torture-workloads.md` and PR #55 status.

- [x] Package the exact source commit/XISO/catalog and register new immutable runner media.
- [x] Run only zero voices, mono/stereo 256 voices, and the 257 denial on upstream and candidate with the same settings. Inspect complete guest receipts and all counts/output/cleanup fields. Keep failed cases attributable; do not silently rerun the full family.
- [x] Document hashes, run IDs, guest verdicts, runner qualification limitations, and remaining 93 cases. Push the draft branch without force. This partition does not complete PR #55.

## Behavior Research

Comparative OSS research: public MCPX field definitions and xemu VP behavior identify 256 slots, 64 HRTF-sensitive slot indices, 32-sample frames, linked voice handles, S16/stereo fields, and CPU-visible current offsets. These compatibility constants are necessary. No reference implementation expression is copied. The existing repository owns its raw session and family integration. A 257-frame constant source avoids loop-position aliasing while keeping PCM decoding and channel/count output deterministic; the matrix does not fix the source length for scaling cases.
