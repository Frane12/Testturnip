# Turnip-Drnas A830 S2-BW1 — INTERNAL DRAFT

Experimental A830 bandwidth/tile-memory build derived from **S2-D2 Upstream 2026-10-07**.

## What changed

### 1. A830 GMEM eligibility envelope

The older SMART-GMEM helper originated on A810 and still had a 2 MiB physical-GMEM sanity ceiling. On A830 that can reject otherwise valid runtime metadata before the Smart/PROFILED selector gets a chance to use it.

BW1 widens only that sanity envelope to **16 MiB**. It does not hard-code an A830 allocation size: Mesa's runtime-reported physical GMEM, usable GMEM, selected layout and allocator limits remain the source of truth.

### 2. Bandwidth/tile-memory prior

BW1 adds an A830-only structural prior using:

- Mesa's existing SYSMEM vs GMEM attachment bandwidth-per-pixel estimates;
- the allocator-selected tile area;
- selected tile occupancy relative to layout capacity;
- estimated tile count for the real render area;
- draw reuse density per tile;
- live attachment bytes and plane count.

The prior only adjusts the existing SMART structure score. It does **not** program GMEM offsets, registers, barriers, resolves or synchronization.

### 3. Existing measured logic remains authoritative

S1/S2-D2 measured PROFILED history, the tail learner, sparse audit behavior and the exact A830 GMEM safety gate are retained. A strong measured SYSMEM result can still win.

## A/B controls

No variable is required for the first run.

- `TU_FRANE_A830_BW1=1` — default, enable BW1 prior.
- `TU_FRANE_A830_BW1=0` — disable only BW1.
- `TU_FRANE_A830_FOOTPRINT=0` — disables the S2-D2 footprint metadata path; BW1 then has no selected-tile metadata and naturally becomes inactive.
- `TU_FRANE_A830_GMEM=0` — full A830 GMEM safety fallback to SYSMEM.

## Suggested first tests

Use the same Winlator/DXVK settings and Max Frame Latency state as the current A830 baseline. Compare at least two warm runs per title and watch for:

- average FPS and 1%/frametime smoothness;
- power draw;
- RAM growth;
- square/color artifacts;
- KGSL page faults or device loss.

Recommended first titles: Crysis/CryEngine, Far Cry 3 and GTA IV.

**Status:** host-policy tested + Android ARM64 compile gate. No claim of on-device stability or performance until A830 hardware results exist.
