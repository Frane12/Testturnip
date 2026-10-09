# A830 S2-BW2 — Adaptive Tile Cost

Experimental A830 branch layered on S2-BW1.

## Goal

BW1 opened the old A810-era 2 MiB sanity ceiling so A830 multi-MiB GMEM metadata
can participate in the selector. BW2 does not increase or fake GMEM capacity.
Mesa remains authoritative for physical/usable GMEM, tile layout, attachment
offsets, barriers, resolves and synchronization.

BW2 adds a cost model built from:

- selected tile pixels and allocator capacity;
- estimated replay/tile count;
- GMEM vs SYSMEM attachment bandwidth-per-pixel;
- draw reuse per selected tile;
- live attachment bytes and plane count;
- existing A830 per-render-pass measured tail history;
- existing measured GMEM runtime state.

A strong repeated SYSMEM win triggers a fast per-render-pass rollback with sparse
GMEM audits. A strong repeated GMEM win strengthens the prior but does not remove
control audits.

## A/B

- `TU_FRANE_A830_BW2=1` default.
- `TU_FRANE_A830_BW2=0` disables BW2 only.
- `TU_FRANE_A830_BW1=0` disables the BW1 contribution.
- `TU_FRANE_A830_FOOTPRINT=0` disables allocator-selected tile metadata, so
  BW1/BW2 naturally become inactive.
- `TU_FRANE_A830_GMEM=0` remains the complete GMEM fallback.

## Safety boundary

BW2 is policy only. It does not write GMEM addresses, change physical capacity,
choose unsafe attachment offsets, alter synchronization or modify cache-register
programming.

## First device tests

Use the same Winlator/DXVK configuration and Max Frame Latency state as the A830
baseline. Run at least two warm runs in Crysis/CryEngine, Far Cry 3 and GTA IV.
Compare average FPS, frametime distribution, power, RAM growth and any square/
color artifacts or KGSL faults.
