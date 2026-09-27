# Frane Mesa 26.3.20 A810 GMEM-TURBO EXP

Built directly on the green 26.3.19 A810 MEMORY-AUDIT stack.

This final A810 experiment deliberately leaves the empirically good adaptive
IR3 texture window at its default 12 and keeps the safe LRZ shader-change
dirtying rule.  The only new risk is a more aggressive SMART-GMEM decision
policy.

## What changes

When measured timing confidence, render-pass structure and the live PROFILED
decision all agree that GMEM is favorable, the driver holds GMEM longer:

- strongest agreement: SYSMEM control probe 1/256;
- strong agreement: 1/128;
- moderate agreement: 1/64.

Before the timing state is armed, strong structural evidence can push the
exploratory SYSMEM probability down to a 4% floor and requests timing samples
at 1/8 cadence so the measured state converges faster.

The control probes are still measured, so adverse evidence can flow back into
the existing 26.3.4 hysteretic confidence state.

## A/B

Default: `TU_A810_26320_GMEM_TURBO=1`

Baseline fallback: `TU_A810_26320_GMEM_TURBO=0`

The opt-out keeps the complete 26.3.19 stack but restores the exact 26.3.18
SMART-GMEM decision policy.

## What to watch

Use the same FC3/Warhead scene and settings as the reference build.  Compare
low FPS, frametime stability and GPU usage first.  Because this intentionally
keeps GMEM selected longer, immediately note any sun/lighting flicker, colored
tiles, rectangular corruption or a regression after several minutes.  If one
appears, retest with `TU_A810_26320_GMEM_TURBO=0` to isolate the new policy.
