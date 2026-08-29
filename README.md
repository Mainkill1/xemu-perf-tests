xemu-perf-tests
====

Provides tests intended to be used to detect performance improvements/degradation in
the [xemu](xemu.app) project.

# Usage

Tests will be executed automatically if no gamepad input is given within an initial timeout.

Individual tests may be executed via the menu.

# Controls

DPAD:

* Up - Move the menu cursor up. Inside a test, go to the previous test in the active suite.
* Down - Move the menu cursor down. Inside a test, go to the previous test in the active suite.
* Left - Move the menu cursor up by half a page.
* Right - Move the menu cursor down by half a page.
* A - Enter a submenu or test. Inside a test, re-run the test.
* B - Go up one menu or leave a test. If pressed on the root menu, exit the application.
* X - Run all tests for the current suite.
* Y - Toggle between one shot and continuous test mode. In continuous mode, tests are designed to run near the edge of
  60 FPS on 1.0 Xbox devkit hardware, provided that the application is built in release mode and XBDM notifications are
  not attached.
* Start - Enter a submenu or test.
* Back - Go up one menu or leave a test. If pressed on the root menu, exit the application.
* Black - Exit the application.

# Test configuration

Behavior can optionally be determined via a JSON configuration file loaded from the XBOX.

```json
{
  "settings": {
    "disable_autorun": false,
    "enable_autorun_immediately": false,
    "enable_shutdown_on_completion": false,
    "skip_tests_by_default": false,
    "delay_milliseconds_between_tests": 0,
    "measurement_iterations_multiplier": 1,
    "output_directory_path": "e:/xemu_perf_tests"
  }
}
```

`measurement_iterations_multiplier` scales the fixed measured iteration count
of every selected test without changing its warmup count. A host runner can use
a short baseline-only calibration to choose enough fixed work for a sustained
15-30 second measurement, then reuse that exact multiplier for all baseline and
candidate runs. Valid values are 1 through 100000. Never calibrate the candidate
independently, because that would compare different amounts of guest work.

In the default release build, the program will look for this file in the `output_directory_path` (
`e:/xemu_perf_tests/xemu_perf_tests_config.json`) and `d:\xemu_perf_tests_config.json`, taking whichever is found
first.

When building from source, the `sample-config.json` file in the `resources` directory can be copied to
`resources/xemu_perf_tests_config.json` and modified in order to change the default behavior of the final xiso.

#### Filtering test suites/cases

The `"test_suites"` section may be used to filter the set of tests.

For example, suppose the program contains four test suites: `Default suite`, `Unlisted suite`, `Skipped suite`, and
`Suite with skipped test`. Each test suite contains two tests, `TestOne` and `TestTwo`. Without any filtering, the menu
tree would be something like:

```
Run all and exit
Default suite
  TestOne
  TestTwo
Unlisted suite
  TestOne
  TestTwo
Skipped suite
  TestOne
  TestTwo
Suite with skipped test
  TestOne
  TestTwo
```

___Note___: The names used within `"test_suites"` and its children are the same as the names that appear in the
`xemu_perf_tests` menu.

By default, any descendant of the `"test_suites"` object that contains a `"skipped": true` will be omitted.

For example, the following config will disable all tests except

```json
{
  "settings": {},
  "test_suites": {
    "Skipped suite": {
      "skipped": true,
      "TestOne": {}
    },
    "Suite with skipped test": {
      "TestTwo": {
        "skipped": true
      }
    },
    "Default suite": {
      "TestOne": {}
    }
  }
}
```

Resulting in

```
Run all and exit
Default suite
  TestOne
  TestTwo
Unlisted suite
  TestOne
  TestTwo
Suite with skipped test
  TestOne
```

This behavior may be modified via the `"skip_tests_by_default"` setting, allowing only entries with an explicit
`"skipped": false` to be retained. For example, the following config will disable all tests except the `TestOne` case
under `Default suite`.

```json
{
  "settings": {
    "skip_tests_by_default": true
  },
  "test_suites": {
    "Default suite": {
      "TestOne": {
        "skipped": true
      }
    }
  }
}
```

`GameLoadComposite` also provides `08-LongUnlockedScene`. It is one XBE test
case with ordered CPU, PFIFO, alpha/overdraw, streaming/surface-reuse,
combined, and full-system stages. Each stage has an independent guest marker
window while the normal test-case filter can select it by name:

```json
{
  "settings": { "skip_tests_by_default": true },
  "test_suites": {
    "GameLoadComposite": {
      "08-LongUnlockedScene": { "skipped": false }
    }
  }
}
```

Optional root `game_load_composite.long_unlocked_scene` settings keep the
global values as their backward-compatible defaults while allowing calibration
per retained stage. Stage mask bits are CPU=1, PFIFO=2, alpha/overdraw=4,
streaming/surface-reuse=8, combined=16, and full-system=32. `stages` is an
optional named-list filter intersected with `stage_mask`.

```json
{
  "game_load_composite": {
    "long_unlocked_scene": {
      "stage_mask": 63,
      "stages": { "cpu": true, "pfifo": true, "alpha_overdraw": true,
                  "streaming_surface_reuse": true, "combined": true, "full_system": true },
      "measurement_iterations_multiplier": { "cpu": 12, "pfifo": 4, "alpha_overdraw": 8 },
      "warmup_iterations": { "cpu": 1, "pfifo": 0 },
      "gpu_precondition": { "alpha_draws": 8192 }
    }
  }
}
```

Omitted stage multipliers/warmups inherit the global settings. The fixed,
untimed GPU precondition runs once immediately before the first retained GPU
stage; `alpha_draws: 0` disables it. Each retained stage writes a normal result
record with its applied warmup/multiplier and precondition metadata. The final
`GameLoadComposite::08-LongUnlockedScene` result is an intentionally extra
summary record (`kind: game_load_composite_long_scene_summary` and
`exclude_from_stage_window_mapping: true`); consumers must map F0/F1 windows
only to `kind: game_load_composite_long_scene_stage` records.

`GameLoadComposite` also provides `09-CrossTitleHotpath`. It keeps one
asset-free XBE busy with eleven fixed stress slices that match current title
discovery fronts: queued vertex CPU writes, PGR2-like small draws, texture
update reuse, surface reuse, pipeline-state churn, constant-blend-color
reuse, repeated unchanged texture-binding reuse, PGR2 inline-element pressure,
scaled surface pressure, S3TC texture rewrites with a wait after every draw,
and a matching GPU-wait control without texture or draw work.
The same XISO accepts a closed runtime job object and can run either a short
smoke or sustained fixed work without changing the known input/output contract.

Checked-in host configs can narrow that one test to a title-like shape. Current
PGR2 lag representation is `suite/configs/cross-title-pgr2-lag-representative.json`,
which selects small draws + texture reuse + surface reuse + pipeline churn +
blend-constant reuse + repeated unchanged texture-binding reuse.

```json
{
  "settings": { "skip_tests_by_default": true },
  "test_suites": {
    "GameLoadComposite": {
      "09-CrossTitleHotpath": { "skipped": false }
    }
  },
  "game_load_composite": {
    "cross_title_hotpath": {
      "fast_smoke": false,
      "stage_mask": 127,
      "stages": {
        "queued_vertex_cpu_writes": true,
        "pgr2_small_draws": true,
        "texture_update_reuse": true,
        "surface_reuse": true,
        "pipeline_state_churn": true,
        "blend_constant_reuse": true,
        "texture_binding_reuse": true
      }
    }
  }
}
```

The final `GameLoadComposite::09-CrossTitleHotpath` record is the summary.
Longer sustained runs are the evidence path. Short runs stay for smoke only,
because small windows can hide stalls and give defunct numbers.

Cross-title bit 512 is reported as `s3tc_streaming_fenced_draws`. The legacy
job key `s3tc_streaming_burst` remains accepted, but output never uses that
ambiguous name. Each sustained invocation performs 384 DXT1/DXT3/DXT5 guest
texture rewrites and draws, plus 385 declared `gpu_waits`: one after every draw
to protect the reused guest address and one final measured completion wait.
This is a synchronization-interaction workload, not a decode-only benchmark.
Fixed source and recipe KATs detect input corruption. Smoke mode uses 48 draws
and 49 waits with the same 1:1:1 format ratio.

Cross-title bit 1024 is `gpu_wait_control`. It performs 384 iterations of one
known PGRAPH pattern write, one `WaitForGpu`, and one exact register readback;
smoke mode performs 48. Its `pfifo_methods`, `fence_reads`, and `gpu_waits`
metadata are equal by construction. Comparing this stage with the S3TC stage
separates common guest/PFIFO wait cost from texture decode, upload, and draw
cost. `gpu_waits` counts API calls; it does not claim a fixed number of MMIO
polls inside each call.

Framebuffer provenance remains mandatory. Emulator-produced hashes are
regression oracles, not proof of retail Xbox correctness. Promote an oracle to
`RETAIL_XBOX` only after independent hardware runs of the exact XISO/job agree.

# Building

## Prerequisites

This project uses https://pypi.org/project/nv2a-vsh to build vertex shaders. It may be
installed by running `pip install -r requirements.txt` from this directory.

## CLion

### Building

Under Settings > Build, Execution, Deployment > CMake

- Provide the path to the nxdk toolchain file under CMake Options

  `-DCMAKE_TOOLCHAIN_FILE=$CMakeProjectDir$/third_party/nxdk/share/toolchain-nxdk.cmake`

- Set the `NXDK_DIR` environment variable to the absolute path of the `third_party/nxdk` subdirectory.

- Optionally modify the `PATH` variable to make sure the path to your chosen version of Clang comes first.

### Debugging

#### Using [xemu](xemu.app)

1. Create a new `Embedded GDB Server` target
1. Set the Target to the `<your project name>_xiso` target
1. Set the Executable to the `<your project name>` binary (it should be the only thing in the dropdown)
1. Set `Upload executable` to `Never`
1. Set `'target remote' args` to `127.0.0.1:1234`
1. Set `GDB Server` to the path to the xemu binary
1. Set `GDB Server args` to
   `-s -S -dvd_path "$CMakeCurrentBuildDir$/xiso/xemu-perf-tests_xiso/xemu-perf-tests_xiso.iso"` (the `-S` is
   optional and will cause xemu to wait for the debugger to connnect)
1. Under `Advanced GDB Server Options`
1. Set "Working directory" to `$ProjectFileDir$`
1. On macOS, set "Environment variables"
   to
   `DYLD_FALLBACK_LIBRARY_PATH=/<the full path to your xemu.app bundle>/Contents/Libraries/<the architecture for your platform, e.g., arm64>`
1. Set "Reset command" to `Never`

#### Using [xbdm_gdb_bridge](https://github.com/abaire/xbdm_gdb_bridge) and a devkit/XBDM-enabled Xbox

1. Create a new `Embedded GDB Server` target
1. Set the Target to the `<your project name>_xiso` target
1. Set the Executable to the `<your project name>` binary (it should be the only thing in the dropdown)
1. Set `Upload executable` to `Never`
1. Set `'target remote' args` to `127.0.0.1:1999`
1. Set `GDB Server` to the path to the xbdm_gdb_bridge binary (e.g., `<some_path>/xbdm_gdb_bridge`)
1. Set `GDB Server args` to `<your_xbox_ip> -v3 -s -- gdb :1999 e:\$CMakeCurrentTargetName$`
1. Under `Advanced GDB Server Options`, set `Reset command` to `Never`

To perform automatic deployment after builds:

1. Under the `Before launch` section, click the `+` button and add a new `Run external tool` entry.
1. Set the `Description` field to something like `Sync program and resources to the XBOX`
1. Set the `Program` field to the path to the xbdm_gdb_bridge binary (same as above)
1. Set `Arguments` to
   `<your_xbox_ip> -- mkdir e:\$CMakeCurrentTargetName$ && %syncdir $CMakeCurrentBuildDir$/xbe/xbe_file e:\$CMakeCurrentTargetName$ -f`
1. Set `Working directory` to `$ProjectFileDir$`

## Adding new tests

The `utils` directory has a script that may be used to generate a skeletal test suite.

### Documentation

Autogenerated documentation may be accessed
at [https://abaire.github.io/xemu-perf-tests](https://abaire.github.io/xemu-perf-tests/)

Some special Doxygen comments are used to describe test results on the website:

1. A detailed description attached to the `TestSuite` subclass (see `high_vertex_count_tests.h`)
2. Ideally a list of `@tc` custom commands in the documentation for the constructor method, explaining what each test is
   doing and/or is expected to display (see `high_vertex_count_tests.cpp`).

---

**NOTE:** For tests whose class name is not equal to the lower case version of the `suite_name` string passed to the
`TestSuite` constructor, a `kSuiteName` `private static constexpr const char *` should be created, containing the
`suite_name` value passed to the `TestSuite`. The documentation generation script will pick this up to allow downstream
scripts to discover the test metadata.

---

### Using nv2a log events from [xemu](https://xemu.app/)

1. Enable tracing of nv2a log events as normal (see xemu documentation) and exercise the event of interest within the
   game.
1. Duplicate an existing test as a skeleton.
1. Add the duplicated test to `CMakeLists.txt` and `main.cpp` (please preserve alphabetical ordering if possible).
1. Use [nv2a_to_pbkit](https://github.com/abaire/nv2a_to_pbkit) to get a rough set of pbkit invocations duplicating the
   behavior from the log. Take the interesting portions of the converted output and put them into the body of the test.
   You may wish to utilize some of the helper methods from `TestHost`   and similar classes rather than using the raw
   output to improve readability.

### Writing nv2a vertex shaders in assembly

See [the README in the nv2a_vsh_asm repository](https://github.com/abaire/nv2a_vsh_asm) for an overview.

`*.vsh` files are assembed via the `generate_nv2a_vshinc_files` function in CMakeLists.txt. Each vsh file produces a
corresponding `.vshinc` file that contains a C-style list of 32-bit integers containing the vertex shader operations.
This file is intended to be included from test source files to initialize a constant array which may then be used to
populate a `VertexShaderProgram` via `SetShader`.

For example:

```c++
// Note that the VertexShaderProgram does not copy this data, so it is important that it remain in scope throughout
// the use of the VertexShaderProgram object.
static const uint32_t kPassthroughVsh[] = {
#include "passthrough.vshinc"
};

// ...

  auto shader = std::make_shared<VertexShaderProgram>();
  shader->SetShader(kPassthroughVsh, sizeof(kPassthroughVsh));
  host_.SetVertexShaderProgram(shader);

```

Uniform values may then be set via the `VertexShaderProgram::SetUniform*` series of functions. By default, the 0th
uniform will be available in the shader as `c96`.

For example, a shader that takes a 4-element vertex might have the code:

```asm
#vertex vector 96
```

which would be populated via

```c++
  shader->shader->SetUniformF(0, -1.f, 1.5f, 0.f, 1.f);
```
