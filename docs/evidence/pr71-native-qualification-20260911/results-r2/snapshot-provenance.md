# PR71 retail snapshot provenance and qualification limit

| Workload | Saved-state name | Authoring xemu source | Seed SHA-256 | Original verification |
| --- | --- | --- | --- | --- |
| PGR2 snapshot | `vm-20260907142321` | `67178d0af1e9b7e4a4019dd5c2c77e9045ae8b3b` | `cbc17b468d49127a09743a63777ee3bef35b63040083989187724cd4a42b594c` | PASS at authoring, September 7 |
| Morrowind snapshot | `vm-20260905015459` | `bc60883c4ef05912c5b4b29051ba64341f576b15` | `d178ecc4154abad5fc7cb9e428f380a1c8d49d20cbed66ba552eaaa6ed7514ad` | Verified at authoring, September 5 |

Both seeds predate fixed baseline `9f618d6d8c4c446ef023955f3d4de22f661f61a4` and previous main `5edff26383c6440da35bc92b9fca35f4a404b03b`. The NV2A saved-field declarations and post-load hook did not change in the inspected source diffs from either authoring commit to previous main, but many renderer implementations did. That source check does not establish equal runtime cost after loading an old snapshot.

The existing campaign passes the *same* immutable seed to every comparison role. Its snapshot timing can identify a paired difference under that input, but alone cannot establish that freshly reached gameplay has the same performance. The PGR2 full-start run avoids `-loadvm`; the maintained full XISO separately tests functional output, not retail frame pacing.

If snapshot timing determines merge acceptance, author new PGR2 and Morrowind checkpoints with the nominated current main at the intended in-game states, on separate disposable seed copies. Record producer source/executable and seed SHA-256, validate guest state and reproducible progression, then rerun previous main, candidate Hybrid Off/On, and fixed baseline against each *same new seed*. Keep these original seed identities and results; do not replace or overwrite them. If the new source changes guest-visible behavior, describe that difference rather than treating a freshly authored seed as an identical workload by default.
