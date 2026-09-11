# Follow-up: execution order and avoidable timer scheduling work

**Status: source/order review complete; retained scheduler-trace attribution in progress. PR59 remains draft/HOLD.** No product change, build, new gameplay benchmark or baseline move has been made in this follow-up.

## Execution order is a real limitation of the maximum-interval comparison

The second OpenGL run has the larger maximum interval in **all five pairs**, whichever executable occupies that position. The recorded completion/start timestamps confirm the declared execution order. B is the retained baseline and AM the combined repair.

| Pair | Execution order | First max (ms) | Second max (ms) | Second-vs-first improvement |
| ---: | --- | ---: | ---: | ---: |
| 1 | B → AM | 51.343 | 67.316 | -31.110% |
| 2 | AM → B | 52.934 | 62.604 | -18.268% |
| 3 | B → AM | 56.068 | 58.637 | -4.582% |
| 4 | AM → B | 55.518 | 60.941 | -9.768% |
| 5 | B → AM | 52.460 | 54.664 | -4.201% |

Maximum interval has raw direction `+bad`. These percentages compare **second position against first position**, not candidate against baseline. Negative is unfavorable. The median second-position maximum improvement is −9.768%. This is a descriptive association in five sequential pairs, not a measured causal order penalty or a corrected patch estimate.

OpenGL p99 is worse in second position in only 3/5 pairs; Vulkan p99 in 2/5. The five-for-five maximum pattern must not be generalized to those metrics. The original candidate-vs-baseline Vulkan p99 result (median −2.249%, adverse beyond 2% in 3/5 pairs) remains unresolved. We have not subtracted an assumed order effect, discarded a slow run, or declared an optimization pass.

[All position comparisons and source hash](order-analysis.json), [replay script](analyze-run-order.py). Run `python3 docs/evidence/pr59-ptimer-attribution-20260910/analyze-run-order.py` from the evidence repository root to reproduce the JSON. The data comes from the already-published `fec867ab` run records; this is not another emulator run.

## Source findings and qualifications

| Reviewed concern | Verified conclusion | Missing measurement |
| --- | --- | --- |
| ACK rebuilds host schedule | Every ACK reconciles before W1C and attempts scheduling; armed/running/enabled cases calculate and modify the timer | Actual equal-deadline requeue count and ACK frequency |
| Canceling an absent timer | Inactive schedule branch still calls deletion; generic deletion takes the list mutex and scans even when absent | Number of redundant deletions and list traversal length |
| Broader IRQ work | Final updater now covers additional register writes; **baseline ACK already called the same broad updater once** | Calls versus effective transitions and added cost |
| Deadline arithmetic | Baseline already used wide multiplication; careful replacement is not merely introducing wide arithmetic | Avoidable calculation frequency and generated-code cost |
| Windows wait interaction | Candidate configuration includes the existing XBOX short-spin/rounded-poll path | Actual deadline distribution, spin/sleep durations and dispatch delay |
| Notification from requeue | Conditional on head insertion and notification/coalescing state | Timer rearm is not an observed OS wakeup |

The [source audit](source-review.md) pins `c17591d5`, runtime `8da17c3e`, and test-only head `0043629b`, including code locations, ownership and counter/test plans. [Build configuration](poll-build-config.json) confirms `-DXBOX=1`, no `CONFIG_PPOLL`, and Windows in the retained candidate's configured build. No binary was rebuilt.

The narrowest promising later change is an ACK-specific no-op path: retain pre-W1C reconciliation and final IRQ publication; skip recalculation/requeuing only when the alarm epoch did not advance and serialized, valid PTIMER-owned state proves the required host timer is still present. An inactive timer already known absent could also avoid repeated cancellation. Callback consumption, reset and post-load must invalidate derived host state. A generic same-computed-deadline cache skips queue work but still pays the arithmetic. This is a conditional design, **not an implemented or performance-qualified fix**.

## Retained-trace work

The assigned analysis uses existing ETLs, serialized exports with automated admission, and no new emulator launches. The first export confirms a WPR steady-state marker can arrive roughly 100 ms after the controller's recorded measurement boundary. The marker alone is therefore not a valid frame-window origin. The trace analysis is checking retained QPC/UTC anchors against the trace-header origin and recording clock-alignment limitations before attributing running, ready and waiting time.

No CPU/IRQ/timer/wakeup totals are claimed here while that extraction is underway. The prior [report](REPORT.md) and all original data remain available; its hold decision is unchanged. The completed trace findings and next measured diagnostic step will be added separately to this evidence branch.
