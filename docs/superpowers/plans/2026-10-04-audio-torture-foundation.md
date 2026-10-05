# Audio Torture Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish hardware-compatible case identity, safe raw MCPX ownership, and one executable S16 control leaf on PR #55; this is partition 1 of the approved 138-case design, not completion of the other 137 cases.

**Architecture:** Generate immutable guest descriptors from the existing 138-case matrix. Keep register admission/teardown policy independent of Xbox APIs so host tests can exercise failures; use the existing PCI/BAR probe as the hardware adapter. Register one opt-in S16 leaf only after device-observed progress, output checking, and cleanup are available.

**Tech Stack:** Python 3 host contracts, C++17/NXDK guest code, CMake Release XISO, Deck xemu through Xemu-Test-Runner.

**Spec:** `docs/superpowers/specs/2026-10-04-hardware-compatible-audio-torture-design.md`

## Global Constraints

- Keep PR #55 draft. Do not merge or describe 138 cases as implemented after this foundation slice.
- The XISO must use guest-visible Xbox PCI/BAR/MMIO, with no emulator-private command or fixed xemu-only APU base.
- A result passes only on observed device progress, case-specific output/state oracle, and verified teardown; source hashes and elapsed time are insufficient.
- Device access and DMA memory remain guarded if quiescence cannot be proved. Ordinary failures produce leaf records rather than fatal assertions.
- Preserve the user-owned dirty `third_party/nxdk` checkout; build in a separate directory and stage only explicit files.
- Current available native host is Deck/xemu; original-Xbox execution is not claimed.
- The full PR still requires all 138 cases, including 0-voice and 257-allocation boundary cases, on the same branch in later plans.

## Review Focus

1. Absent PCI device or invalid BAR must fail before any register write — Task 2 tests this through fake discovery.
2. Busy VP/GP/EP or nonempty voice lists must reject ownership without altering state — Task 2 tests the busy snapshot.
3. Timeout after DMA arm must retain the allocation and stop later audio work — Task 3 tests timeout cleanup.
4. A source checksum plus inferred frame count must never appear as observed completion — Task 3 tests result provenance.
5. Ordinary setup/output/teardown failures must produce a selected leaf record — Task 4 tests each failure path.

---

### Task 1: Generate the complete guest case contract

**Files:**
- Create: `src/tests/audio_case_descriptor.h`
- Create: `src/generated/audio_case_catalog.inc`
- Create: `utils/generate_audio_guest_cases.py`
- Create: `tests/test_audio_guest_case_contract.py`
- Modify: `src/tests/audio_torture_backend.h`
- Test: `tests/audio_case_catalog_probe.cpp`

**Interfaces:**
- Consumes: `build_cases(matrix)` and `validate(matrix, cases)` from `utils/audio_torture_cases.py`.
- Produces: `const AudioTorture::AudioCaseDescriptor *AudioTorture::FindAudioCase(const char *id)` and a generated table with exactly 138 IDs. `AudioCaseDescriptor` holds `const char *id`, `BackendKind backend`, typed `WorkloadSpec workload`, `bool expected_allocation_denial`, `uint32_t allocation_attempt_count`, a 15-family `OracleProfile` enum, and `const char *intended_paths_json`.
- Extends `WorkloadSpec` with the matrix's missing typed fields: buffer/refill sample counts, 3D voice count, pipeline mode, mixed-format/rate flags, and allocation-attempt count. Extend `SignalKind` for the two near-Nyquist inputs. Existing fields keep their meanings.

- [ ] **Step 1: Write failing host contract tests**

  In `tests/test_audio_guest_case_contract.py`, require `--check` to reject a stale generated file; compile and run `tests/audio_case_catalog_probe.cpp` with `g++ -std=c++17` and assert 138 unique IDs, both backends, exact `audio.vp_scaling.s16_mono.v001`, the 0-voice descriptor, and `allocation_attempt_count == 257` with expected denial. Assert that no descriptor is marked executable by default.

- [ ] **Step 2: Verify red**

  Run `python3 -m unittest tests.test_audio_guest_case_contract -v`. It must fail because the generator/table and probe interface do not exist.

- [ ] **Step 3: Implement the typed descriptor and deterministic generator**

  `generate_audio_guest_cases.py` maps every matrix parameter to a typed field or rejects it; it emits positional C++17 initializers, a canonical manifest digest, and no runtime JSON parser. `--check` compares bytes without writing. The first generator run writes the checked-in include file.

- [ ] **Step 4: Verify green and existing contracts**

  Run `python3 -m unittest tests.test_audio_guest_case_contract tests.test_audio_torture_contract -v`, `python3 utils/generate_audio_guest_cases.py --check`, and `python3 utils/audio_torture_cases.py --check`; all must pass with 138 descriptors.

- [ ] **Step 5: Commit**

  Stage only the six Task 1 paths and commit `Generate typed guest descriptors for 138 audio cases`.

### Task 2: Prove admission and restoration policy without Xbox hardware

**Files:**
- Create: `src/tests/audio_apu_ownership.h`
- Create: `src/tests/audio_apu_ownership.cpp`
- Create: `tests/audio_apu_ownership_probe.cpp`
- Create: `tests/test_audio_apu_ownership.py`
- Modify: `src/tests/audio_mcpx_apu_device.h`
- Modify: `src/tests/audio_mcpx_apu_device.cpp`

**Interfaces:**
- Consumes: `McpxApuRegisterSnapshot`, `McpxApuPciInfo`, and the existing read-only PCI/BAR mapper.
- Produces: `ApuOwnershipDecision CheckApuOwnership(const McpxApuRegisterSnapshot &, const VoiceListSnapshot &)` and `bool ApuStateRestored(const ApuStateSnapshot &, const ApuStateSnapshot &)`. `ApuRegisterIo` exposes `bool Open(std::string &error)`, `uint32_t Read32(uint32_t offset) const`, `bool Write32(uint32_t offset, uint32_t value)`, and `void Close()` so host fakes and the real PCI/BAR adapter share one contract. The real adapter adds bounded, aligned writes only for explicitly admitted register ranges; it never writes during probing.
- `VoiceListSnapshot` includes every VP list top and the GP/EP reset state needed by the admission decision, not only the eight values in the existing probe snapshot.

- [ ] **Step 1: Write failing policy and fake-device tests**

  Compile `tests/audio_apu_ownership_probe.cpp` from `tests/test_audio_apu_ownership.py`. Assert: idle empty lists permit ownership; active engine, released GP or EP, nonempty list, or an `Open` failure reject before a write. In the real-adapter contract, pin absent PCI identity, I/O BAR, 64-bit BAR, and disabled PCI memory decoding as `Open` failures. Assert that a mismatched post-state denies DMA release.

- [ ] **Step 2: Verify red**

  Run `python3 -m unittest tests.test_audio_apu_ownership -v`; it must fail on missing policy/interface, not on a compiler configuration error.

- [ ] **Step 3: Implement pure policy, then the narrow hardware adapter**

  Use only guest-visible register state. Keep policy functions free of Xbox headers. Add a fake-write log in the host probe and verify that rejected admission has zero writes. The real adapter validates alignment and the 0x80000 BAR aperture before every write.

- [ ] **Step 4: Verify green and cross-build**

  Run the focused host test and the normal Release XISO build. If an exact engine-control value is not supported by public behavior evidence, do not guess it here; keep that write out of the adapter until Task 3's single-voice test proves it.

- [ ] **Step 5: Commit**

  Stage only Task 2 paths and commit `Guard MCPX ownership and register access`.

### Task 3: Execute and observe one raw S16 voice safely

**Files:**
- Create: `src/tests/audio_mcpx_raw_backend.h`
- Create: `src/tests/audio_mcpx_raw_backend.cpp`
- Create: `src/tests/audio_s16_control_oracle.h`
- Create: `tests/audio_raw_s16_probe.cpp`
- Create: `tests/test_audio_raw_s16.py`
- Modify: `src/tests/audio_torture_backend.h`
- Modify: `src/CMakeLists.txt`

**Interfaces:**
- Consumes: Task 1 descriptor `audio.vp_scaling.s16_mono.v001`, its deterministic S16 fixture, Task 2 ownership policy and PCI/BAR adapter.
- Produces: `bool McpxRawBackend::Run(const AudioCaseDescriptor &, WorkloadResult &, std::string &error)` and `bool S16ControlOracle::Check(const S16ControlObservation &)`. Construct `McpxRawBackend` with injected `ApuRegisterIo &` and `AudioDmaAllocator &`; the allocator interface provides `void *Allocate(size_t bytes)`, `uint32_t PhysicalAddress(const void *pointer)`, and `void Free(void *pointer)`. `WorkloadResult` distinguishes submitted samples, observed engine-frame progress, observed voice terminal state, and the output oracle; it never converts source length into an observed completion count.
- The backend retains DMA allocation when a timeout or failed stop leaves ownership uncertain, and exposes `cleanup_passed=false` to the caller.

- [ ] **Step 1: Write failing host tests for the S16 oracle and lifecycle**

  In `tests/audio_raw_s16_probe.cpp`, feed a fake register transport with known progress and mix output. Assert a PASS only after the expected S16 output tolerance and stop/readback; assert FAIL for no progress, wrong output, busy admission, and failed stop. Assert failed stop does not call the allocation-free hook. In `tests/test_audio_raw_s16.py`, compile and run the probe.

- [ ] **Step 2: Verify red**

  Run `python3 -m unittest tests.test_audio_raw_s16 -v`; it must fail because the raw backend/oracle are missing.

- [ ] **Step 3: Implement the smallest Xbox-compatible raw S16 sequence**

  Use the public guest-visible APU contract and all 256 frames of fixture `vp.s16.mono.48k.256`, with no hard-coded xemu mode or host address. Configure one voice and one mixbin, observe a finite sample/frame-progress register and guest-readable output, then stop/unlink before restoring saved state. If public behavior cannot establish a safe control value, stop this task for design review rather than transplanting the xemu-only fixture's experimental mode.

- [ ] **Step 4: Verify green, then compile both modes**

  Run the focused host probe and `python3 -m unittest discover -s tests -q`; build both normal Release XISO and the opt-in audio XISO. A compile success is not a guest PASS.

- [ ] **Step 5: Commit**

  Stage only Task 3 paths and commit `Add observed raw S16 audio control`.

### Task 4: Expose one truthful opt-in leaf and preserve failures

**Files:**
- Create: `src/tests/audio_torture_tests.h`
- Create: `src/tests/audio_torture_tests.cpp`
- Create: `tests/test_audio_s16_leaf_contract.py`
- Modify: `src/main.cpp`
- Modify: `src/runtime_config.cpp`
- Modify: `src/CMakeLists.txt`
- Modify: `utils/test_catalog.py`
- Modify: `resources/catalog.json` and generated catalog/plan artifacts through the repository generator only

**Interfaces:**
- Consumes: Task 1 descriptor and Task 3 backend/result.
- Produces: `AudioTortureTests::S16MonoControl()` selected by `audio.vp_scaling.s16_mono.v001`, gated by the existing xemu-only opt-in only for Deck development while the guest implementation remains hardware-compatible. The leaf records oracle, observed completion, and cleanup metadata in the normal `TestHost::FinishDraw` result path.

- [ ] **Step 1: Write failing host contract tests**

  Assert that the default plan excludes the new leaf, the opt-in resolved plan includes exactly this implemented audio ID, 137 planned IDs remain absent, and setup/output/teardown failures each call the result-record path with `oracle_status=FAIL`. Assert an ordinary failure cannot exit through `ASSERT` before a record.

- [ ] **Step 2: Verify red**

  Run `python3 -m unittest tests.test_audio_s16_leaf_contract -v`; it must fail on missing registration/result behavior.

- [ ] **Step 3: Implement the gated suite and generated catalog entry**

  Use the repository's existing generated-catalog workflow. Mark this first leaf correctness-only until the native oracle and timing conditions qualify performance. Keep the development bootstrap separate and do not register its reference-backend timing as this leaf.

- [ ] **Step 4: Verify green and complete local gate**

  Run `python3 -m unittest discover -s tests -q`, fixture and descriptor `--check`, catalog `--check`, `git diff --check`, and both Release XISO builds. Record the exact commands and results in the PR.

- [ ] **Step 5: Commit**

  Stage only Task 4 paths and generated artifacts; commit `Register opt-in raw S16 audio correctness leaf`.

### Task 5: Prove the first leaf on the Deck without overclaiming

**Files:**
- Modify: `docs/audio-torture-workloads.md`
- Modify: PR #55 description/evidence comment only after the run is retained

**Interfaces:**
- Consumes: the exact Task 4 XISO, catalog, source commit and Deck runner API.
- Produces: immutable receipts for one selected leaf on a pinned upstream xemu reference and the candidate, or a precise failure/runner limitation report. No other planned leaf is promoted by this run.

- [ ] **Step 1: Package the exact XISO and pin identities**

  Run `utils/package_runner_suite.py` with the built ISO and source commit. Record ISO/catalog digests, xemu executable digests, runner version, settings, and selected ID.

- [ ] **Step 2: Execute only `audio.vp_scaling.s16_mono.v001` through the runner**

  Use the runner's XISO selection API with unique attempt IDs for upstream and candidate. Require a complete selected-leaf receipt, not a screenshot or launch status alone.

- [ ] **Step 3: Inspect and classify**

  Compare guest oracle metadata, observed progress, output, guard and teardown. Preserve both run artifacts. A timeout, missing record or differing output leaves the PR draft and becomes a focused diagnosis; do not widen to 138 native runs yet.

- [ ] **Step 4: Document evidence and commit**

  Update the audio workload document with the exact first-leaf evidence and explicit original-Xbox limitation. Commit the documentation; push the non-force branch update to PR #55 after verifying its remote head has not moved.

## Subsequent plans required for the same PR

After this foundation passes, write separate detailed plans for the remaining four partitions in the approved spec: raw VP format/rate/scaling/memory; streaming/modes/DSP; test-owned AC'97; and ceiling/full 138-case qualification. Every plan must retain TDD, lifecycle, portable oracle and native evidence gates. PR #55 does not become ready or merge from completion of this foundation alone.
