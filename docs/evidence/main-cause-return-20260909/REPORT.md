# Returned guest addresses identify the interrupt-shadow polling loop

**Over 99% of sampled NULL dispatcher returns land at two adjacent guest-kernel instructions in an interrupt-shadow polling loop.** Both renderer captures passed. This establishes where repeated dispatcher work occurs; it does not establish that removing it improves gameplay or that either return is optional.

Base main `bd1fecb93353272dda2a810991e28945de35b665`; diagnostic head `504a7e72637fb54787f01db2a254265a85433548`; tree `3286d98b8b2d82ee358d0abc90fdd07be509426f`. [Draft xemu #54](https://github.com/Mainkill1/xemu/pull/54) was published before build/testing. Executable SHA-256 `34c9f1537973c44a0a97d592f3fbaaea87782da34f289614db7c61e68bdf32b3`.

| In-window periodic samples | Vulkan | OpenGL |
| --- | ---: | ---: |
| Total sampled NULL returns | 39,262 | 14,289 |
| Next PC `0x8001b02f`, interrupt shadow set | 19,614 | 7,131 |
| Next PC `0x8001b030`, interrupt shadow cleared | 19,609 | 7,121 |
| Share at these two sites | 99.90% | 99.74% |
| Sample-table overflow | 0 | 0 |

The sampler records next-dispatch PC and flags once per 4093 NULL returns into at most 512 per-thread buckets. Counts above are cumulative last-minus-first inside the recorded UTC window. They are periodic samples and may be biased, not statistical confidence intervals. First/last sampled timestamps, all sites and overflow are retained in each return summary. Sample totals multiplied by 4093 match same-thread NULL counter differences within one sampling period (differences 1485 Vulkan, 182 OpenGL). The paired counter snapshots are explicitly identified; output timestamps differ because emission itself takes time.

The sampled flags differ only by `HF_INHIBIT_IRQ`. A separate paused-guest inspection maps the first address to the NOP immediately after STI, and the second to the following NOP before CLI. The loop checks work state and returns to STI when no work is available. No guest instruction is being skipped by these diagnostics. The sampler's `first_tb_pc=0` reflects PC-relative translation-block metadata and is not a claim that guest execution began at address zero. The first TB in a chain is also not necessarily its final exiting TB.

## Consequence for the next experiment

The existing return after clearing the interrupt shadow permits pending IRQ delivery and must remain. The bounded candidate to evaluate is dynamic lookup immediately after STI establishes the shadow, entering the existing shadow-keyed one-instruction block. It must retain the second return, cache-miss fallback, debugger/exit-request handling, TF/RF and consecutive-shadow semantics. MOV/POP SS are outside the initial scope. This requires its own main-based draft and actual interrupt regressions before acceptance; an address-count change alone would not qualify it.

The [preceding state-helper capture](../main-cause-state-20260909/REPORT.md) ruled out flag/FPU helper volume as the dominant explanation. Dirty-memory scans remain a separate optimization opportunity, with no safe basis for suppressing repeated clears solely because an earlier scan armed nothing.

## Validation and reproducibility

One unchanged 20-second Morrowind snapshot cell per renderer completed through the GUI test session. Both final scenes were inspected and showed the expected outdoor bridge/buildings, crosshair and no pause/reconnect overlay. Nonblack checks, seed hashes and private-disk/process cleanup passed. This is not an independent pixel or audio oracle. Cause lookup accounting passed on both exact UTC windows. The existing O2/LTO build options, symbols and assertions were retained. No baseline was rebuilt; no full XISO/PGR2/resource campaign or guest suite change occurred.

Diagnostic emission noticeably perturbs timing. Cadence and tails are preserved in the run JSONs and must not be compared to uninstrumented baseline values as an optimization result. The private guest-inspection step first encountered unsupported HMP instruction disassembly, then read only 128 virtual bytes in a second short inspection session and decoded them locally. Both sessions were cleaned up. These were code inspections, not repeated performance measurements. Guest bytes/disassembly, game assets, private configuration and full application logs are not published.

[Manifest](manifest.json), [patch](diagnostic.patch), [Vulkan run](vulkan-run.json), [OpenGL run](opengl-run.json), [Vulkan cause summary](vulkan-cause-summary.json), [OpenGL cause summary](opengl-cause-summary.json), [Vulkan return summary](vulkan-return-summary.json), [OpenGL return summary](opengl-return-summary.json).

Raw numeric records: [Vulkan causes](vulkan-counters.jsonl), [Vulkan returns](vulkan-returns.jsonl), [OpenGL causes](opengl-counters.jsonl), [OpenGL returns](opengl-returns.jsonl). The existing checked cause analyzer consumes the cause JSONL. The [dataset-specific return recipe](analyze_return_samples.py) accepts a minimal log reconstructed from these two numeric streams and the exact UTC bounds in each summary. It assumes this diagnostic schema; it is not a general untrusted-log validator. Check that `period_phase_bound_pass` is true in the generated summary.

To reconstruct the minimal log for either renderer in this directory:

```python
import json
from pathlib import Path
renderer = 'vulkan'  # or opengl
rows = []
for suffix, prefix in [('counters', 'XEMU_CAUSE '), ('returns', 'XEMU_RETURN ')]:
    for line in Path(f'{renderer}-{suffix}.jsonl').read_text().splitlines():
        row = json.loads(line)
        rows.append((row['utc_us'], prefix, row))
rows.sort(key=lambda item: (item[0], item[1]))
Path('minimal.log').write_text(''.join(prefix + json.dumps(row) + '\n'
                                      for _, prefix, row in rows))
```

Then run `python3 analyze_return_samples.py --stderr minimal.log --start-utc-us START --end-utc-us END --cause-jsonl regenerated-causes.jsonl --return-jsonl regenerated-returns.jsonl --output regenerated-summary.json`. Use `window.start_utc_us`/`window.end_utc_us` from the selected summary. Both published return summaries regenerate byte-for-byte from the sanitized numeric streams.
