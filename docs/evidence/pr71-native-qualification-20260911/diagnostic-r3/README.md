# PR71: route selection attribution (diagnostic only)

The instrumented source `a9f856eb56c67ea417b2115d10cbbdf54e141511` was based on product head `e6048469f7f461ea8f0c91a4efe98f8331c9b8ce`; its Windows executable SHA-256 is `d6a47e9aae5c11bf4eb6c2c7484c2e29893a1937cf2f39b4b35e452380d3d954`. This 30-second PGR2 Vulkan snapshot pair ran in interactive Session 1, with separate shader-cache profiles. Both cells passed, retained guest progression, and completed automated cleanup. Instrumentation changes timing; these figures cannot qualify a product release or explain the isolated 667 ms cold stall.

| Timed region per guest frame (+bad) | Hybrid Off | Hybrid On | Improvement % |
| --- | ---: | ---: | ---: |
| `pipeline_prepare` | 10.162 ms | 11.429 ms | -12.468% |
| `bind_shaders` | 4.813 ms | 6.149 ms | -27.758% |
| `select_fragment_route` | 0.187 ms | 1.574 ms | -741.711% |
| `pack_uber_controls` | 0.000 ms | 0.288 ms | n/a |
| `module_specialized_create` | 0.001 ms | 0.001 ms | +0.000% |
| `module_fallback_create` | 0.000 ms | 0.000 ms | n/a |
| `pipeline_fallback_miss` | 0.000 ms | 0.000 ms | n/a |

The route selector ran 3,078 times/frame Off and 3,078 times/frame On. The extra 1387.1 μs/frame is of the same scale as the additional shader-binding and pipeline-preparation time. `pack_uber_controls` is nested inside route selection; these rows must not be added together. The pair recorded no fallback-module creation and no fallback-pipeline misses, so it characterizes specialized-ready draw work, not cold fallback creation.

The follow-up product repair checks the existing specialized module/binding before packing fallback controls and promotes a borrowed LRU hit without a second lookup. Its source and tests are in [PR #71](https://github.com/Mainkill1/xemu/pull/71). The revised full XISO and retail campaign is isolated as `campaign-r2`; its results must determine performance acceptance.

Selected sanitized counters and exact identities are in [route-attribution.json](route-attribution.json). Raw frame telemetry remains on the test host.
