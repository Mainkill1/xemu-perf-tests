# Performance PR graphs and metric tables

Each open PR has a source-labelled metric/status chart, a metric table, and a diagram explaining the code or test flow. Baseline/candidate identities and qualification limits travel with the data. Where no performance comparison exists, charts explicitly show validation counts or unavailable measurements; they do not invent FPS or resource results. Existing detailed PR evidence remains intact.

Bars use independent axes with their actual units and start at zero. Baseline and candidate/observed colors identify the source, not improvement or regression. Missing values are not zero. Historical and current-head measurements must not be combined into one qualification claim.

| PR | Chart | Source data |
| --- | --- | --- |
| [xemu-10](https://github.com/Mainkill1/xemu/pull/10) | [PNG](charts/xemu-10.png) | [JSON](data/xemu-10.json) |
| [xemu-11](https://github.com/Mainkill1/xemu/pull/11) | [PNG](charts/xemu-11.png) | [JSON](data/xemu-11.json) |
| [xemu-14](https://github.com/Mainkill1/xemu/pull/14) | [PNG](charts/xemu-14.png) | [JSON](data/xemu-14.json) |
| [xemu-15](https://github.com/Mainkill1/xemu/pull/15) | [PNG](charts/xemu-15.png) | [JSON](data/xemu-15.json) |
| [xemu-16](https://github.com/Mainkill1/xemu/pull/16) | [PNG](charts/xemu-16.png) | [JSON](data/xemu-16.json) |
| [xemu-18](https://github.com/Mainkill1/xemu/pull/18) | [PNG](charts/xemu-18.png) | [JSON](data/xemu-18.json) |
| [xemu-2](https://github.com/Mainkill1/xemu/pull/2) | [PNG](charts/xemu-2.png) | [JSON](data/xemu-2.json) |
| [xemu-25](https://github.com/Mainkill1/xemu/pull/25) | [PNG](charts/xemu-25.png) | [JSON](data/xemu-25.json) |
| [xemu-37](https://github.com/Mainkill1/xemu/pull/37) | [PNG](charts/xemu-37.png) | [JSON](data/xemu-37.json) |
| [xemu-48](https://github.com/Mainkill1/xemu/pull/48) | [PNG](charts/xemu-48.png) | [JSON](data/xemu-48.json) |
| [xemu-5](https://github.com/Mainkill1/xemu/pull/5) | [PNG](charts/xemu-5.png) | [JSON](data/xemu-5.json) |
| [xemu-51](https://github.com/Mainkill1/xemu/pull/51) | [PNG](charts/xemu-51.png) | [JSON](data/xemu-51.json) |
| [xemu-54](https://github.com/Mainkill1/xemu/pull/54) | [PNG](charts/xemu-54.png) | [JSON](data/xemu-54.json) |
| [xemu-55](https://github.com/Mainkill1/xemu/pull/55) | [PNG](charts/xemu-55.png) | [JSON](data/xemu-55.json) |
| [xemu-57](https://github.com/Mainkill1/xemu/pull/57) | [PNG](charts/xemu-57.png) | [JSON](data/xemu-57.json) |
| [xemu-58](https://github.com/Mainkill1/xemu/pull/58) | [PNG](charts/xemu-58.png) | [JSON](data/xemu-58.json) |
| [xemu-6](https://github.com/Mainkill1/xemu/pull/6) | [PNG](charts/xemu-6.png) | [JSON](data/xemu-6.json) |
| [xemu-7](https://github.com/Mainkill1/xemu/pull/7) | [PNG](charts/xemu-7.png) | [JSON](data/xemu-7.json) |
| [xemu-8](https://github.com/Mainkill1/xemu/pull/8) | [PNG](charts/xemu-8.png) | [JSON](data/xemu-8.json) |
| [xemu-9](https://github.com/Mainkill1/xemu/pull/9) | [PNG](charts/xemu-9.png) | [JSON](data/xemu-9.json) |
| [xemu-perf-tests-7](https://github.com/Mainkill1/xemu-perf-tests/pull/7) | [PNG](charts/xemu-perf-tests-7.png) | [JSON](data/xemu-perf-tests-7.json) |
| [xemu-perf-tests-9](https://github.com/Mainkill1/xemu-perf-tests/pull/9) | [PNG](charts/xemu-perf-tests-9.png) | [JSON](data/xemu-perf-tests-9.json) |

## Reproduce

With Python and `matplotlib==3.10.6` installed:

```sh
python render_pr_charts.py data charts
```

[Manifest](manifest.json) records exact data/image hashes. Charts summarize existing evidence; they do not rerun tests. The descriptor-candidate report additionally preserves its newly completed focused GL/VK cells and rejected staging attempt. No guest suite or XISO image changed.
