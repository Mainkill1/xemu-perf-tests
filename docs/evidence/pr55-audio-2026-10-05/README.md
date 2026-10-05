# PR 55 targeted Deck evidence

These files are byte-exact copies collected before the requested Deck cleanup
on 2026-10-05. They cover only four boundary leaves, not all 45 implemented leaves
or all 138 planned cases. See [the handoff](../../pr55-audio-handoff.md) for pinned
build/image identities, work settings and interpretation limits.

| File | Original run | SHA-256 |
| --- | --- | --- |
| [Upstream guest results](upstream-results.txt) | `20261005-085633811-73f576269693440bbcbe72e27c230c90` | `8817542626d4f3d57382cf9116412a70d9a5c45849baeeb83ca25d57d3c8beaa` |
| [Candidate guest results](candidate-results.txt) | `20261005-085722185-03bf09d8dd5f49da895bbae551bd8c44` | `fa2ae149c85f9db26901eca374f866c635662ce501689b7bec9b7e4a3f3a259e` |
| [Upstream assessment](upstream-assessment.json) | upstream run above | `fe564c67c85f4ee21407f75d8c4756722c9dee8029734681f1ceb2baf48648d7` |
| [Candidate assessment](candidate-assessment.json) | candidate run above | `fe564c67c85f4ee21407f75d8c4756722c9dee8029734681f1ceb2baf48648d7` |

All four guest leaves pass on both builds. Runner execution and evidence checks
pass, but correctness fails and comparisons remain ineligible because pinned
oracles are missing. Neither host-output quality, comparable performance nor
original-Xbox behavior is qualified. Do not regenerate or normalize these files.
Older Deck diagnostics and upstream run directories were authorized for deletion;
the candidate is the last run retained on the device.
