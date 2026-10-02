# Drnas Turnip A830 V59 — LRZ-CLEAN

Hardware target: **Snapdragon 8 Elite / Adreno 830**.

Base: **Drnas Turnip A830 V2 ADAPTIVE-GMEM** on the same pinned Mesa 26.3-devel
snapshot used by that validated A830 branch.

This is not a blind A810 V59 rename.  Only the portable LRZ ideas are translated
and they are gated to the known A830 chip IDs:

- `0x44050000`
- `0x44050001`
- `0xffff44050000`

## Ported V58/V59 LRZ behavior

1. **FS-hazard LRZ retention.** If an A830 draw must skip LRZ because of the
   fragment shader but depth writes are disabled, LRZ remains valid. The draw
   temporarily skips LRZ; a later compatible draw can use it again.

2. **Non-sticky stencil LRZ write-disable.** If stencil may kill fragments but
   depth writes are disabled, A830 no longer makes LRZ write-disable sticky for
   the entire render pass. LRZ writes are already off for that draw, and later
   compatible depth-writing draws may resume them.

The existing stencil side-effect protection that can temporarily disable LRZ
testing remains unchanged.

## A830-specific translation policy

The A810 V57/V59 fixed GMEM replay, depth-window and tile thresholds are **not**
ported. A830 keeps the V2 measured adaptive-GMEM learner, real Mesa GMEM
capacity/layout metadata, timing confidence and sparse control probes.

The exact A830 chip check is calculated once per LRZ state calculation and
reused by both translated decisions.

## Safety audit

The build asserts that the prior KGSL wait fixes, queue mutex failure cleanup,
hot-path cache ownership, LRZ dirty correctness and A830 V2 learner are still
present. A810-only PWR_MAX and sampled-depth diagnostics remain A810-only.

No GMEM addresses, allocator rules, barriers, resolves, MSAA safety,
synchronization semantics, WSI mode or undocumented register programming are
changed.

## First test

Run with **no extra variables**. For a clean A/B, compare against your current
A830 V2 build with the same Winlator/FEX/DXVK settings, resolution and game
preset. Far Cry 2 and Dirt 3 are both useful; use consecutive warm runs and
compare average, minimum and visible frametime consistency.
