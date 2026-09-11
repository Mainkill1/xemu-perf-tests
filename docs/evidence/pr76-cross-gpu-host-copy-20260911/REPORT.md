# PR76 cross-GPU host-copy qualification

PR76 head `c40375db7fc274dc097eae71c72d3ee6460dcce8` fixes the
black display seen when xemu renders with the AMD Vulkan adapter while its
OpenGL presentation context remains on NVIDIA. Focused native validation now
passes on both adapters. Performance and broad regression qualification have
not started, so the PR remains draft.

## Cause and correction

The failing release selected AMD for Vulkan and loaded the AMD Vulkan driver,
while the OpenGL context and window remained on NVIDIA. Both GPU engines were
active, but importing the AMD opaque Win32 memory handle into the NVIDIA GL
context produced a black guest display.

The candidate compares the Vulkan device and driver UUIDs with every device
UUID and the driver UUID reported by the GL context. A compatible match keeps
the shared-memory path. A mismatch omits external-memory export/import, copies
the finished Vulkan display-composition image into mapped host memory, and
uploads that image to a regular GL texture. The copied image includes the
selected internal scale and PVIDEO composition.

## Source and build identities

| Role | Commit | Tree | Executable SHA-256 |
| --- | --- | --- | --- |
| Previous main / failing release | `fc8c5dec9c1aa18883e74b57937d7ec90fdea074` | — | `5c27d5310add91901f5a132c38d250492abf3d5eed253c2e6fe8cf63fb764768` |
| PR76 candidate | `c40375db7fc274dc097eae71c72d3ee6460dcce8` | `001ffaca2bc407d25c1519c4805a3765f899896f` | `4cacd9ddd20a6255fd845e871acf5c7cc04df777af10d35d0fcb4c0dcbbb8a46` |

The candidate used the official Windows O2/full-LTO/x86-64-v3 profile with
assertions, unstripped DWARF, a separate debug image, and ordered symbols. The
focused Windows device-selection unit exited successfully.

## Focused native result

Both runs used strict exact-UUID selection through the interactive Windows
desktop session. They captured the xemu client after 20 seconds, parsed the
candidate's atomic GPU record, closed xemu normally, and verified that no xemu
process remained.

| Requested Vulkan GPU | Actual Vulkan GPU | GL presenter | Transport | Client capture | Nonblack sample | Exit / cleanup |
| --- | --- | --- | --- | --- | ---: | --- |
| AMD Radeon(TM) Graphics | AMD Radeon(TM) Graphics | NVIDIA RTX 3070 Ti Laptop | `host_copy` | 1280×960, visibly correct | 22.819% | Graceful / PASS |
| NVIDIA RTX 3070 Ti Laptop | NVIDIA RTX 3070 Ti Laptop | NVIDIA RTX 3070 Ti Laptop | `shared` | 1280×960, visibly correct | 22.819% | Graceful / PASS |

The captures show the same rendered title scene. Their hashes differ because
the animated scene was sampled at different instants. Screenshots and guest
media remain private; `focused-runs.csv` retains dimensions, hashes, and pixel
sample counts.

## Performance status

No performance result is claimed. The compatibility path adds one composed
image readback and one GL upload per presented frame. The same-GPU NVIDIA path
does not execute that copy, but it still needs a matched comparison against
previous main before integration.

| Workload | Path | Metric | Raw + | Previous main | Candidate | Improvement |
| --- | --- | --- | --- | ---: | ---: | ---: |
| Focused startup | AMD Vulkan / NVIDIA GL | Visible guest output | `+good` | FAIL, black | PASS | N/A correctness repair |
| Focused startup | NVIDIA Vulkan / NVIDIA GL | Visible guest output | `+good` | PASS | PASS | N/A correctness control |
| Retail / XISO | NVIDIA shared | Frame performance | `+bad` | Not run | Not run | N/A |
| Retail / XISO | AMD host copy | Frame performance | `+bad` | Unsupported | Not run | N/A |

## Evidence

- `manifest.json` records source, build, toolchain, test identity, and remaining
  gates.
- `build-receipt.json` records verified build options, focused unit status, and
  artifact hashes.
- `focused-runs.csv` contains the two sanitized native run rows.
- `focused/amd-gpu-info.json` and `focused/nvidia-gpu-info.json` are the atomic
  request-versus-actual adapter and presentation records.

The first native wrapper result correctly rendered AMD output and produced the
right GPU record, but the wrapper checked a nonexistent `status` property
instead of schema field `state`. That checker failure is excluded from the
table. The corrected wrapper reran both focused cells once and both passed.
