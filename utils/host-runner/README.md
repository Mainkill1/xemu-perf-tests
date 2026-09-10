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
