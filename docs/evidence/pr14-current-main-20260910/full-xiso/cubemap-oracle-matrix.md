# PR14 restored cubemap oracle matrix

| Build | Renderer | Expected | Observed | Failures | VUIDs | Result |
| --- | --- | --- | --- | ---: | ---: | --- |
| previous-main | opengl | FAIL negative control | FAIL | 10 | 0 | PASS |
| candidate | opengl | PASS | PASS | 0 | 0 | PASS |
| previous-main | vulkan | PASS | PASS | 0 | 0 | PASS |
| candidate | vulkan | PASS | PASS | 0 | 0 | PASS |

The inherited `report_query.dma_range_guard` failure is tracked separately as xemu issue #60 and is excluded from the PR14 transition above.
