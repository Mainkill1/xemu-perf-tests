# GPU-authored surface to vertex attribute: focused control

The new [guest oracle](https://github.com/Mainkill1/xemu-perf-tests/pull/37) starts with a blue stride-zero diffuse value in CPU vertex memory. A GPU color-surface clear aliases that memory and writes IEEE-754 red (`1, 0, 0, 1`) without a CPU read. The following quad must be red. The untouched background is checked separately. This directly exercises surface readback before CPU vertex-attribute decoding.

Test source `57c2438c3d46c8f99bc18004f1fd34a5d9ed82b9`, XISO SHA-256 `6a57961a7312bb8ec125181ac5e642d194835df382cbb900c81efaf9765536cd`, catalog SHA-256 `ea881a43ec71cc37f74e5863e00f0cf4caea94e32933a5a15063e179e743ddfb`. The ISO was compiled with pinned NXDK `73c95900965a16be3a3e34b8d4d5d41bc18498be` and Clang 19.1.7. Catalog generation/check, 160 host tests, and the ISO build passed. Every cell below used that same image/catalog, one focused guest iteration, scale 1, no host telemetry, and the same SHA-checked runner `cd51e2192bf51a5e58862b4ff5f356867119a59c95351bc3a1378994e7917558`.

| Renderer | Product source / executable SHA-256 | Guest result | Drawn pixel | Background | New VUIDs |
| --- | --- | --- | --- | --- | ---: |
| Vulkan | Main `9148241de690` / `6857240d6e95` | **FAIL** | Blue `FF0000FF` | Correct | 0 |
| Vulkan | #85 `0883fb63009c` / `e9d763da0e02` | **PASS** | Red `FFFF0000` | Correct | 0 |
| Vulkan | #89 tested `150d74ac5525` / `29eac8120cce` | **PASS** | Red `FFFF0000` | Correct | 0 |
| OpenGL | Main `9148241de690` / `6857240d6e95` | **FAIL** | Blue `FF0000FF` | Correct | n/a |
| OpenGL | #89 tested `150d74ac5525` / `29eac8120cce` | **FAIL** | Blue `FF0000FF` | Correct | n/a |

The current #89 head `cbb3b4372f75` has the same Git tree as tested `150d74ac5525`. The main→#85 Vulkan failure/pass pair is a direct negative control for the readback-order repair. The OpenGL failure is inherited from main and is tracked separately; it is not a regression from #85–#89. Its source binder decodes the CPU value after a zero-byte stride-based upload check without first downloading a dirty overlapping GPU surface.

These are **correctness results, not timing results**. They do not resolve the adverse PGR2 snapshot p99, prove a Morrowind map traversal, or cover the remaining #89 forced-finish/stale-repair edges. [Sanitized result rows](results/gpu-surface-vertex-oracle.json) retain exact identities and observed pixels. The runner closed every xemu/trace process after each cell.
