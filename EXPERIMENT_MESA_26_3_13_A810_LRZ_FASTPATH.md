# Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP

Layered directly on 26.3.12 DUAL-TEX-PREFETCH.

This experiment does **not** relax the core LRZ correctness rules. It targets
two places where Turnip can do unnecessary LRZ work or conservatively classify
a draw as unsafe even when the actual color attachments do not require that.

## 1. Sparse color-attachment LRZ classification

Turnip counts the number of defined color attachments, but the old partial-write
check compares the number written against `cb->attachment_count`.

That means a renderpass with holes/undefined RT slots can be treated as a
partial color write even when every real attachment is fully written. In that
case LRZ write can be disabled for the rest of the renderpass unnecessarily.

26.3.13 compares against the number of **defined** color attachments instead.

It also defers the logic-op destination-read check until after confirming that
at least one real color attachment is written. A stale/enabled logic-op state
with zero actual color writes therefore no longer throws away LRZ.

Real blending, partial channel masks, disabled writes on real attachments and
logic ops that actually touch a color target remain conservative.

## 2. A810 fragment-shader LRZ signature fast path

Upstream marks `TU_CMD_DIRTY_LRZ` every time a different fragment shader is
bound.

But LRZ/depth-plane state only depends on a small set of FS properties. On A810,
26.3.13 compares exactly the fields consumed by
`tu6_calculate_lrz_state()` and `tu6_build_depth_plane_z_mode()`:

- writes depth position;
- early-fragment-tests;
- depth layout;
- discard/kill;
- sample-mask writes;
- LRZ status;
- force-late-Z;
- sample shading;
- dynamic depth input-attachment usage.

If two different fragment shaders have the same signature, the new shader is
still bound normally (`TU_CMD_DIRTY_FS` remains), but the redundant LRZ/depth
plane draw-state rebuild is skipped.

This is aimed at DXVK/D3D11 workloads that switch many material/texture fragment
shaders while keeping the same depth behavior.

## A/B switch

Default: enabled.

`TU_A810_26313_LRZ_FASTPATH=0`

restores the previous LRZ blend classification and the old "every FS switch
dirties LRZ" behavior in the same binary.

## What to watch

Use the same FC3 scene/settings as 26.3.12.

Compare default versus `TU_A810_26313_LRZ_FASTPATH=0` for:

- low-FPS floor in vegetation/overdraw-heavy scenes;
- frametime while rotating the camera;
- high-FPS peaks / CPU-limited areas;
- shadows and depth-related artifacts;
- missing geometry or flicker;
- GPU hang/fault.

The expected gain is mostly lower command/state overhead plus better LRZ
retention in sparse color-attachment cases. It should not change the visible
image.
