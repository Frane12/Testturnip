# Frane Mesa 26.3.9 A810 GEN8-GMEM-DIM EXP

Experimental A810 build layered directly on the verified 26.3.8 HOTPATH-V2 baseline.

## Scope

This build implements one narrow Gen8 TODO in Turnip's GMEM bin-size programming. On A8xx, Mesa programs:

- eight `RB_MRT_GMEM_DIMENSION` registers;
- `RB_DEPTH_GMEM_DIMENSION`;
- `RB_STENCIL_GMEM_DIMENSION`.

Upstream currently writes the active tile width/height into every one of those registers and leaves TODO comments that inactive buffers should receive `0x0`.

26.3.9 changes only that state on A810 classic render passes.

## Safety design

The experiment is intentionally conservative:

- **A810 only** (chip IDs `0x44010000` / `0xffff44010000`);
- **classic render passes only**;
- dynamic rendering keeps 26.3.8 behavior because attachment-location remapping may change after begin;
- the MRT mask is the **union of every non-custom-resolve subpass**, so a buffer used only by a later subpass is never zeroed;
- custom resolve subpasses are ignored because Turnip routes those through sysmem;
- depth dimension stays active if any GMEM subpass uses a depth aspect;
- stencil dimension stays active if any GMEM subpass uses either depth or stencil, matching the upstream TODO semantics.

No register write is removed. Inactive dimension registers are still written, but with the exact zero value described by the Gen8 TODO.

## A/B switch

Default: enabled.

`TU_A810_2639_GMEM_DIM_GATING=0`

disables only this 26.3.9 experiment and restores the 26.3.8 all-dimensions behavior in the same driver.

## Deliberately unchanged

- 26.3.8 64-slot borrowed hot-RP path;
- 26.3.7 core fastpath;
- 26.3.5 shader/pipeline/NIR-cache path;
- 26.3.4 GMEM runtime and PROFILED autotuner decisions;
- GMEM allocation/layout;
- attachment addresses, pitches and formats;
- resolve algorithm;
- sync/KGSL;
- WSI/present path;
- shader generation.

## Test

Best A/B test:

1. same Far Cry 3 save/spot/settings;
2. first run with default 26.3.9;
3. repeat with `TU_A810_2639_GMEM_DIM_GATING=0`;
4. compare gameplay FPS, frametime stability, menu FPS, RAM, artifacts and hangs.

Because both runs use the exact same binary, differences are isolated to the new Gen8 dimension gating.
