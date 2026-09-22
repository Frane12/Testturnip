# Frane Turnip V15-O / A810 SMART GMEM + LEAN MEMORY

## Provenance and scope

Built from the **V15-N A830 source branch**, with an additional A810-only patch, not a rename of an A830 blob. Mesa 26.1.4, exact upstream source commit pinned in the workflow. The A830 logic is deliberately unchanged; the new A810 handling recognizes `0xffff44010000` and Android KGSL `0x44010000`. Other GPUs do not receive A810 policy. A810's approximately 576 KiB physical GMEM makes it very different from the A830: no A830 hardware size or register assumptions are copied into the A810 configuration. Original Mesa synchronisation, UBWC, gralloc, attachment loads/stores and BO lifetimes remain intact.

No proprietary Qualcomm code is imported or linked. This branch does **not** claim to repair CCU underflow, hardware GPU faults, hangs, or missing textures. GMEM use on A810 is an experimental cost decision; runtime validation on actual device is mandatory.

## Profiles — restart the game/container between mode changes

| Flag | Mode |
|---|---|
| `TU_A810_GMEM_PROFILE=0` | Disable custom A810 Smart GMEM policy. For explicit all-SYSMEM baseline also set `TU_AUTOTUNE_ALGO=prefer_sysmem` or Winlator's SYSMEM option. |
| `TU_A810_GMEM_PROFILE=1` (default) | Conservative Smart GMEM: at least 12 draws, known cost samples, 320×180..1280×800 pixels, max **8** estimated full-layout tiles, **22%** projected entry traffic savings + per-tile penalty. |
| `TU_A810_GMEM_PROFILE=2` | Experimental: >=10 draws, up to 1600×900 pixels and **16** tiles, **15.5%** predicted entry saving + lower per-tile penalty. More GMEM can be slower or artifact-prone. |

Both profiles preserve existing memory tiers: suspend optional GMEM below 1280 MiB `MemAvailable`, resume above 1792 MiB, caution below 2560 MiB; 2 profitable observations before enabling a renderpass, 3 percentage-point hold hysteresis. `TU_AUTOTUNE_ALGO` remains an explicit override. A810 disables the experimental V15-L *dense-pass reduction* of the tile penalty. It retains generic low-draw caution and Mesa's mandatory hardware safety conditions.

## Lean allocation A/B

| Flag | Effect |
|---|---|
| `TU_A810_LEAN_BUDGET=0` | Restore the V15-G 70% advisory memory budget; default A810 **60%**. Budget does not limit physical allocations. |
| `TU_A810_LEAN_CACHE=0` | Restore original retention of a single free autotune BO; default does not retain one if >64 KiB **and** the existing Mesa last-reference test allows it. |
| `TU_A830_*` | Retain original V15-N A830 behavior; the A810 settings do not change it. |

## Test plan

Use a previously working A810 SYSmem driver available as rollback. Start `TU_A810_GMEM_PROFILE=0` / SYSMEM with 960×544 or 1024×768 at your familiar FEX, DXVK, wine, RAM limits; then restart using default profile=1 at the **same** settings. Once visually verified and 15+ minutes stable, test profile=2. Compare FPS, frame-time/1% lows, 15/30-minute Android RAM, artifacts, background textures and GPU resets. If graphics fail, immediately revert to SYSMEM. A cross compile alone is not a working-device guarantee.

Upstream community examples note small GMEM/cache on A810 and historical CCU-related fixes and recommend controlled tests, not unconditional GMEM.
