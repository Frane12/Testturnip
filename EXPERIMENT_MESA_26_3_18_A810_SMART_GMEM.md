# Frane Mesa 26.3.18 A810 SMART-GMEM EXP

26.3.18 keeps the successful 26.3.17 adaptive IR3 scheduler and adds a new
A810-only GMEM decision layer.

## Default

`TU_A810_26318_SMART_GMEM=1` is ON by default.

To recover the 26.3.17 measured-only GMEM policy:

`TU_A810_26318_SMART_GMEM=0`

## What is new

The older runtime waited for measured GMEM/SYSMEM timings before promoting
GMEM. 26.3.18 also consumes information Mesa already knows when the render pass
is recorded:

- `sysmem_bandwidth_per_pixel`
- `gmem_bandwidth_per_pixel`
- real FULL-layout pixels per GMEM tile
- estimated number of tiles for the render area
- render-pass drawcall count / draw density

These produce a bounded structural score. Before enough timing samples exist,
a strong score biases the existing PROFILED probability toward GMEM but never
eliminates SYSMEM exploration and never fights a profiler already strongly
favoring SYSMEM.

Once measured timing has armed the runtime, timing remains authoritative.
Probe cadence then adapts to confidence:

- marginal GMEM winner: one measured SYSMEM control probe per ~32 decisions
- strong winner: ~1/64
- maximum timing confidence + strong structural agreement: ~1/128

This reduces unnecessary control passes when GMEM is repeatedly and clearly
better, while keeping a path to self-disarm if scene behavior changes.

## Correctness scope

No changes to attachment offsets, GMEM allocation, LRZ, barriers, Vulkan
synchronization, descriptor state, or tile load/store implementation.

The 26.3.17 adaptive IR3 scheduler remains enabled with its default max texture
window of 12.
