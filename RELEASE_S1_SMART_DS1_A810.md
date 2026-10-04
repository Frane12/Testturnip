## A810 S1 Smart DS1 — internal experiment

V38 GMEM allocation/search and the exact S1 Smart 2 baseline, with a depth/stencil validation layer and stable Smart decision ownership.

- Record requested depth and stencil LOAD/CLEAR/STORE/NONE semantics separately. Check the resulting Mesa packed or separate-plane operations before admitting GMEM.
- Prove positive, aligned GMEM plane offsets, capacity and non-overlap once when a simple render pass is created. Reuse the cached proof during selection; inspect the chosen layout and full-frame geometry at recording time.
- Keep depth/stencil transfers unconditional on A810 while DS1 is active, including empty tiles. Preserve native Mesa clears, transfers, LRZ safeguards, barriers and GPU command emission.
- Admit validated D24S8, D32S8 and S8 paths, with conservative full-frame, single-layer, single-subpass and single-sample restrictions. Unsupported cases return to SYSMEM before allocating measurement history where applicable.
- Include per-aspect operations in scene identity so depth/stencil variants cannot share a Smart vote merely because their combined LOAD/STORE flags match.
- Preserve authoritative Smart GMEM/SYSMEM choices and paired measurements. The old forced-depth heuristic may operate only between measurements when Smart has not taken ownership; stencil passes use measured selection.
- Retain the two previously integrated Mesa correctness fixes and V38 packing. No hardware register workaround or FPS result is asserted.

Enabled by default. Install normally; no extra environment variables are required.

`TU_FRANE_DS1=0` restores the old Smart 2 depth/stencil policy and conditional transfer behavior. `TU_FRANE_SMART=0` disables Smart history selection. `TU_FRANE_STENCIL_LS=0` narrows stencil-preservation admission while retaining DS1 checks.

Validation: 38,656 DS1 policy/geometry/signature combinations, 1,440 cases through the actual Mesa attachment_set_ops function including STORE_OP_NONE and dont_care_as_load, existing 716,040 Smart boundary cases and reversal/cadence simulations, ASan/UBSan, patch application and Android ARM64 compile/link/package checks. See build logs for completed results.

Experimental internal draft. On-device stencil/clear/occlusion correctness, frame times and FPS are still unmeasured. For comparison use complete Crysis runs (three passes), Dirt 3 (two or three runs), and longer gameplay with the same settings. DXVK 1.9.4 remains the comparison baseline unless another version is intentionally tested.
