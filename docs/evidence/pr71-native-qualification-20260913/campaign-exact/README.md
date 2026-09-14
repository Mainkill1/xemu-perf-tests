# PR #71 exact-head campaign recipe

This directory records the configuration and retail schedule deployed to the native Windows test host on 2026-09-13. All other scripts and host-config templates came unchanged from [`campaign-r2`](../../pr71-native-qualification-20260911/campaign-r2/). The full-XISO script had SHA-256 `9c63e8c0ddb265db4c76275156287c8ef605aec44a38fe11dbcafdee0d27fdf8` in both places.

| Identity | Value |
| --- | --- |
| Product runtime commit | `fa00907d08239657e5ec1ec19041df138ab6ae4b` |
| Product tree | `0ee676b3e4b5da8447b322772495fee3847fc703` |
| Win64 executable SHA-256 | `6e8053816aef10597d7f0f4c597c348c5deada28acafb4247327bc80d137f116` |
| Fixed-baseline executable SHA-256 | `3489fdcc593e942b92a612bf35a98f509ff0907e3370e1e5f45f2972d83fb16b` |
| Previous-main executable SHA-256 | `91ca72bddb6ec21441ffbbf3ef5bdddeda84ab3b7768d1f29081dca07136c4b3` |
| XISO source commit | `0044091f59ca148ab3c0bc919add10729bfe0fe3` |
| XISO source tree | `b2dcfae1164d8a2d741be766ee43e6e767c14310` |
| XISO image SHA-256 | `a91fdcc7b87e609a98075dfe9b6225edccb00d6036cfed6a4d7ea644b53d7400` |
| XISO catalog SHA-256 | `a0674f73cef85d43f1dba0ad2059b9fa076841a0f4b1084b59186cf4ffb3871e` |

The XISO schedule compares the fixed baseline, previous main, and candidate with OpenGL and Vulkan, including Hybrid Off/On and cold/warm cache roles. The retail schedule omits the already recorded PGR2 snapshot diagnostic and runs PGR2 fresh/full start followed by the Morrowind snapshot. Each retail workload contains its own baseline, previous-main, candidate-Off, and candidate-On comparison cells. The candidate's optional shader fast path is Off in this primary matrix; it needs a separate explicit On check.

The campaign's expected non-PASS records are inherited oracle expectations. A campaign cell labeled `passed` means its record count, exact binary/image identities, functional outcomes, and expected non-PASS set matched its declared control; it does not mean every individual XISO leaf passed.
