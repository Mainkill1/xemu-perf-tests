# Full-suite xemu-only opt-in

`run-suite-enable-xemu-only-tests.patch` is a generated unified diff for the
exact `run-suite.py` input whose SHA-256 is
`c478e3a38865de180f3751b88904bf18b152dd05208e773326979e3d7b65b64d`.
It must not be applied to a different runner revision.

The patch adds `--enable-xemu-only-tests`. The option is accepted only with
`--mode perf --full-suite`; any other invocation raises a clear request error.
For that accepted invocation, it passes `enable_xemu_only_tests=True` to the
existing `build_perf_config` function, which writes the guest's existing
`settings.enable_xemu_only_tests` boolean. The existing full-suite path still
sets `skip_tests_by_default` to `False`; this patch does not filter the guest
catalog or alter its 154 required records.

The exact patch output has SHA-256
`41813aa9d27495e13291a64aac48abcf19817ffd424b9f0fc2846d5e4e89b54d`.
Applying it to the pinned input produces a runner whose SHA-256 is
`1577e2647044760f86dd61bb154c5d01c789bcc5db9d4904464736fa530be0af`.

Validate the pinned runtime seam after exporting `XEMU_FULL_SUITE_RUNNER` with
the path of an external copy of the exact input:

```sh
python3 -m unittest -v tests/test_host_runner_full_suite.py
```

The test verifies the source digest, applies the versioned patch, imports the
patched parser/configuration paths with dependency stubs, and checks the
accepted and rejected option combinations. It also executes the old pinned
runner and verifies that it rejects the new option and omits the guest boolean.

This is source-level runner validation only. It does not launch xemu or an
XISO, establish guest completion markers, waive any oracle, or demonstrate
that all 154 records pass.

## Direction-normalized improvement reporting

`run-pair-improvement-semantics.patch` is applied after
`run-pair-output-only-forwarding.patch`. The first patch chain must produce the
exact pair runner SHA-256
`7e1a7ccc3fefc259775bffb5ba3198f05b3549b511ca4f342195b07716850e0e`.
The improvement patch has SHA-256
`8e2d0a5bd6704c3bb04cb9c073f259c247e967118d8ba5b1c99f1ddade87df7b`
and produces SHA-256
`2cf2a14e58106ffbf6a784f8f5f1e62cca922ac8a1af4ffdf95700041eb98b38`.

Reader-facing percentages use one sign convention:

| Raw positive marker | Formula | Meaning |
| --- | --- | --- |
| `+good` | `100 × (candidate / baseline - 1)` | A larger raw value is favorable. |
| `+bad` | `100 × (1 - candidate / baseline)` | A larger raw value is unfavorable. |
| `N/A` | No percentage | The metric is contextual or its baseline is zero. |

Positive Improvement % is always favorable and negative is always
unfavorable. Timing, wall-time, CPU-time, scope-total, and scope-unit metrics
use `+bad`. Event counts remain contextual. The JSON output retains raw
baseline/candidate samples, candidate/baseline ratios, ratio confidence
intervals, the legacy raw-sign `median_change_percent`, classifications, and
gate fields. It adds `median_improvement_percent`, a correctly reordered
`improvement_95_ci`, metric direction, and top-level comparison semantics.

Validate the production functions against the exact external runner fixture:

```sh
XEMU_PGRAPH_RUNNER_ROOT=/path/to/pinned/runner \
  python3 -m unittest -v tests/test_host_runner_improvement_semantics.py
```

These controls exercise positive-good and positive-bad metrics, regressions,
neutral and zero-baseline cases, confidence-bound reversal, contextual
counters, backward-compatible raw ratios, and generated Markdown. They do not
launch xemu. Applying this second patch changes the pair-runner digest, so the
existing output-only recipe identities remain valid only for the first patch
chain. Regenerate and review those identities before using both patches in an
output-only paired run.
