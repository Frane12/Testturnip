## A810 S1 Smart DS2 — internal experiment

V38 GMEM allocation/search and the exact S1 Smart 2 baseline, with a depth/stencil validation layer and stable Smart decision ownership.

- Record requested depth and stencil LOAD/CLEAR/STORE/NONE semantics separately. Check the resulting Mesa packed or separate-plane operations before admitting GMEM.
- Prove positive, aligned GMEM plane offsets, capacity and non-overlap once when a simple render pass is created. Reuse the cached proof during selection; inspect the chosen layout and full-frame geometry at recording time.
- Keep depth/stencil transfers unconditional on A810 while DS1 is active, including empty tiles. Preserve native Mesa clears, transfers, LRZ safeguards, barriers and GPU command emission.
- Admit validated D24S8, D32S8 and S8 paths, with conservative full-frame, single-layer, single-subpass and single-sample restrictions. Unsupported cases return to SYSMEM before allocating measurement history where applicable.
- Account for actual D32S8 separate-stencil LOAD/STORE and per-aspect clear bytes in the bandwidth estimate, with A810 and DS1 scope controls.
- Include per-aspect operations in scene identity so depth/stencil variants cannot share a Smart vote merely because their combined LOAD/STORE flags match.
- Preserve authoritative Smart GMEM/SYSMEM choices and paired measurements. The old forced-depth heuristic may operate only between measurements when Smart has not taken ownership; stencil passes use measured selection.
- Retain the two previously integrated Mesa correctness fixes and V38 packing. No hardware register workaround or FPS result is asserted.

Vulkan device name (DXVK HUD): `Turnip-Drnas A810`.

Adaptive changes (DS2):

- Four fixed per-pass load histories: below 64, 256, 1024 draws, and 1024 or more. Each owns its feedback and measurement ticket, so very different loads no longer share one winner.
- Adjacent GMEM/SYSMEM samples must also have comparable draw counts. Distant or mismatched samples cannot form a vote.
- Initial evidence converges after two pairs, or four for persistent depth/stencil and large passes. Two strong opposite pairs can release an established winner without waiting for the old profile average to catch up.
- Refresh the winner every 16 heavy/risky recurrences or 32 normal recurrences. Stable alternative probes remain paired and sparse; two sustained slow winner observations or a large draw change temporarily accelerate pairing.
- Reduce routine probes of a path measured at least twice as expensive. Apply a bounded tail premium to paired measurements; the premium decays with fresh results. Near ties retain a measured deterministic choice and a bounded sampling schedule.
- A single owner handles adaptive selection and timestamp requests; adaptive feedback skips the old overlapping learners. Reuse the creation-time depth/stencil proof and avoid repeating the same recording-time safety check.
- Keep native A810 generic clears, depth/stencil transfers, LRZ, barriers and registers. No empty-tile transfer shortcut is introduced.

`TU_FRANE_ADAPTIVE=0` selects the previous DS1 Smart policy for comparison while retaining DS1 correctness.

Enabled by default. Install normally; no extra environment variables are required.

`TU_FRANE_DS1=0` restores the old Smart 2 depth/stencil policy and conditional transfer behavior. `TU_FRANE_SMART=0` disables Smart history selection. `TU_FRANE_STENCIL_LS=0` narrows stencil-preservation admission while retaining DS1 checks.

Validation: 38,656 DS1 policy/geometry/signature combinations, 1,440 cases through the actual Mesa attachment_set_ops function including STORE_OP_NONE and dont_care_as_load, 256 actual Mesa D32S8 bandwidth cases, 1,048,576 actual guard comparisons (DS1 on/off), 70,200 adaptive boundary cases, 768 abrupt-change simulations with delayed feedback, isolated-load and probe-budget checks, actual Mesa safety-guard equivalence, existing 716,040 Smart boundary cases and reversal/cadence simulations, ASan/UBSan, patch application and Android ARM64 compile/link/package checks. See build logs for completed results.

Experimental internal draft. On-device stencil/clear/occlusion correctness, frame times and FPS are still unmeasured. For comparison use complete Crysis runs (three passes), Dirt 3 (two or three runs), and longer gameplay with the same settings. DXVK 1.9.4 remains the comparison baseline unless another version is intentionally tested.
