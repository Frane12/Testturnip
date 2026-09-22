# Frane Turnip Mesa 26.2.3 -- DiskDVD A8XX code audit (2026-09-22)

## Reproducible base

Mesa 26.2.3 release commit `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2` from `chaotic-cx/mesa-mirror`.
DiskDVD A8XX source inspected: `DiskDVD/A8XX-Y`, branch `A8XX`,
commit `6ccfee74478e63f2993e63697d8b730dd547b03e`.
Our original `patches/port_upstream_main.py` applies Frane V16 for A830 and
Frane V15Q+V17 for A810. Each is a separate build from the **same** Mesa tag.

## What DiskDVD actually does for memory

The DiskDVD `tu_get_budget_memory()` on its A8XX branch uses the Mesa
`vk_physical_device_heap_budget_from_system` helper with an advisory 90%
system-memory fraction. This is a reported budget, not real RAM reserved.
The chosen 26.2.3 Frane branches preserve a more conservative Frane
A830/A810 *advisory* percentage policy rather than claiming DiskDVD has a
RAM recycling/free-lifetime feature. Neither global VkMemory heap size nor
a live BO lifetime is faked.

DiskDVD's `fd6_calc_gmem_cache_offsets` and actual A8XX CCU register
writes still derive from physical GMEM and the kernel/device geometry.
No undocumented cache fraction, fake GMEM cap, unsafe deletion, or A7XX/A6XX
cache-offset trick is transplanted to A8XX. The A8XX CCU register code examined
matches the Mesa 26.2.3 release in the affected section. DiskDVD's broader
shader/compiler and GPU-profile code diverges from upstream and is not
safely interchangeable one file at a time.

## Selected DiskDVD lighting/shader delta

DiskDVD's `src/freedreno/ir3/ir3_compiler.c` explicitly sets
`IR3_DBG_NODESCPREFETCH` when detecting chip `0x44010000` (A810).
We port **only this identified A810-specific codegen workaround** with
a scoped A/B option `IR3_A810_DISKDVD_PREFETCH`. It is ON by default
on A810, never active on A830. Use `IR3_A810_DISKDVD_PREFETCH=0`
to compare against regular 26.2.3 shader compiler behavior.
This is a testable hypothesis for sampled lighting/texture flicker,
NOT a confirmed fix.

Prior tests: sysmem, nolrz, nocb, noubwc, V17 depth-only workaround
failed to resolve the Prince of Persia light flicker; non-GPLAsync DXVK
2.7.1 reduced it. Therefore V17 depth and 100-ms GMEM burst experiments
are retained as OPTIONAL (`TU_A810_SAFE_DEPTH_UBWC=1` /
`TU_A810_GMEM_BURST=1`), both OFF by default in the 26.2.3 A810 build
so shader changes can be tested separately. Our bounded GMEM V15Q stays.

## No on-device claim

CI compilation and ZIP integrity tests do not prove A810/A830 on-device
rendering, memory behavior, FPS, or flicker resolution.
