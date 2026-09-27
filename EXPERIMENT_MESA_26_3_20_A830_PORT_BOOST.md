# Frane Mesa 26.3.20 A830 PORT-BOOST

Experimental A830/8 Elite branch built from the green 26.3.19 MEMORY-AUDIT stack on pinned Mesa `eeca16aa41e89a114e53e76439df623c7efb9519` (26.3.0-devel).

This is a final retarget layer, not a blind A810 rename. The existing 26.3.19 stack is applied and tested first; the last patch enables only the portable 26.3.x optimizations for the exact known A830 IDs `0x44050000`, `0x44050001`, and `0xffff44050000`.

### Default-on A830 layers

- PROFILED turbo cadence and profile-aware low-overhead sampling.
- Measured GMEM runtime plus the 26.3.18 SMART-GMEM structural prior. Measured timings stay authoritative.
- 26.3.7/8 hot render-pass cache fastpath.
- 26.3.9 inactive GMEM-dimension gating.
- 26.3.10 UBO locality.
- Guarded 26.3.11–16 texture-prefetch selection stack.
- 26.3.17 adaptive IR3 pre-RA scheduler; low-pressure texture window remains 12 for the first hardware A/B rather than guessing a larger A830-specific value.
- Bounded RAM-only stage NIR cache with the 26.3.19 32 MiB charged-byte budget and 2 MiB individual serialized payload limit.
- 26.3.19 timing-freshness, hot-cache publication, allocation and overflow fixes.

### Intentional non-ports

A810 sampled-depth/UBWC diagnostics and A810 KGSL PWR_MAX stay A810-only. No A830 register offsets, GMEM addresses, attachment layouts, synchronization rules, descriptor layouts, WSI mode, thermal policy, or undocumented KGSL controls are invented or changed.

### Useful A/B switches

- `TU_A830_26320_PROFILED_GMEM=0`: disable the ported measured PROFILED-GMEM runtime.
- `TU_A830_26320_SMART_GMEM=0`: disable its structural SMART-GMEM prior.
- `TU_A830_26320_CORE_FASTPATH=0`: disable the 26.3.7/8 hot-RP fastpath.
- `TU_A830_26320_STAGE_NIR_CACHE=0`: disable the bounded RAM-only intermediate NIR cache.
- `TU_A830_26317_ADAPTIVE_SCHED=0`: restore upstream fixed scheduler window behavior.
- `TU_A830_26317_TEX_WINDOW_MAX=8..16`: same binary scheduler A/B; default 12.
- `TU_A830_2639_GMEM_DIM_GATING=0`: restore pre-26.3.9 GMEM dimension emission.
- `TU_A830_26313_LRZ_FASTPATH=0`: disable the guarded LRZ-safe pipeline optimization.

No FPS claim is made until A830 hardware measurement. The intended first test is the default configuration with no extra variables.

AI-assisted downstream work; source and full applied diff are published with the binary.
