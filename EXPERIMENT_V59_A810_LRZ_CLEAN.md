# Drnas Turnip V59 — A810 LRZ-CLEAN

Base: **V58 LRZ-KEEP** with the kept V57X `TU_FRANE_EDGE=1` default.

## Goal

Take one additional, bounded LRZ step and simultaneously clean the active Drnas
hot path without changing the proven GMEM/CB/depth/shader policies.

## LRZ step

V58 kept LRZ valid across fragment-shader hazards when depth writes were off.

V59 goes one step further in the stencil path. Upstream makes LRZ write-disable
sticky for the whole render pass whenever stencil can kill fragments. On A8XX,
when depth writes are already disabled, LRZ writes are already off for the
current draw. V59 therefore avoids making that write-disable sticky in that
specific case. Later compatible depth-writing draws may resume LRZ writes.

The existing stencil side-effect guard remains intact, so draws that require LRZ
testing to be temporarily disabled still get that protection. Pre-A8XX behavior
is unchanged.

## Cleanup / audit

The full active Drnas stack is kept functionally intact, but V59 removes two
pieces of repeated hot-path work:

- The V57 depth/stencil load-store predicate is now derived during the existing
  render-pass bandwidth scan and cached in `tu_render_pass`, eliminating a
  second attachment walk in autotune decisions.
- Tail guard + edge mode now share one A810 device check, and `TU_FRANE_EDGE`
  is read once per process instead of on every decision.

The V59 patch also asserts that the earlier KGSL wait fixes, queue mutex-unlock
failure paths, hot render-pass cache ownership fixes, removed random/neural
paths, clean-interface variable removal, and V14 LRZ correctness rollback all
remain present.

## Unchanged

GMEM allocation/offsets, barriers, resolve/MSAA safety, shader scheduler,
concurrent-binning policy, WSI, queue synchronization semantics, V56/V57
selector thresholds, and V58 FS LRZ retention are unchanged.

## Test focus

Use the same Dirt 3 setup and two consecutive runs as V58. Compare average FPS,
minimum FPS, and visible smoothness. If both stay clean, V59 becomes the LRZ
endpoint and the next experiments move to a different module.
