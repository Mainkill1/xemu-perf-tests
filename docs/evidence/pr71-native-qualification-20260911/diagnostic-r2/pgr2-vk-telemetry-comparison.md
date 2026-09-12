# PGR2 Vulkan Hybrid telemetry diagnostic

Diagnostic only; positive duration deltas mean Hybrid On took longer.

| Metric | Hybrid Off | Hybrid On | On - Off | Relative change |
| --- | ---: | ---: | ---: | ---: |
| pipeline_prepare_cpu_us_per_guest_frame | 9652.076 | 11045.214 | +1393.138 | +14.434% |
| flip_stall_wait_us_per_guest_frame | 2210.894 | 2310.225 | +99.331 | +4.493% |
| stalled_wait_us_per_guest_frame | 161.115 | 111.308 | -49.807 | -30.914% |
| total_wait_us_per_guest_frame | 10654.628 | 11205.203 | +550.575 | +5.167% |
| submit_cpu_us_per_guest_frame | 273.885 | 276.894 | +3.008 | +1.098% |
| guest_frames | 872.000 | 865.000 | -7.000 | -0.803% |
