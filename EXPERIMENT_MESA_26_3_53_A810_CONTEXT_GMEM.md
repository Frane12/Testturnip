# Drnas Turnip V53 — CONTEXT-GMEM

Experimental A810 branch built on V52 CLEAN-INTERFACE and a refreshed Mesa
26.3.0-devel snapshot.

## What V53 changes

V53 replaces the single-axis "prefer GMEM" idea with a bounded context score.
The score combines:

- tile footprint / estimated tile count
- attachment count and number of GMEM-resident attachments
- depth/stencil lifetime across subpasses as a depth-reuse proxy
- expected color/depth resolve count
- Mesa's GMEM vs SYSMEM per-pixel bandwidth estimates
- render-pass draw density
- measured GMEM timing hysteresis from the existing runtime state machine
- Mesa PROFILED temporal SYS/MEM probability

The output uses a dead-band. Ambiguous passes keep the prior Mesa/V52 choice.
Only a clear positive or negative score overrides the mode.

## Temporal stability

V53 does not re-measure on every scene change. A strong measured winner uses a
rare opposite-mode control probe, normally 1/256 and up to 1/512 decisions.
Unarmed cases use at most 1/128 exploration while learning.

This is meant to preserve responsiveness to a genuinely changed workload
without turning the autotuner itself into a frametime source.

## Controls

- `TU_FRANE_CONTEXT_MODE=1` — default balanced policy.
- `TU_FRANE_CONTEXT_MODE=2` — lower GMEM entry threshold for aggressive A/B.
- `TU_FRANE_CONTEXT_MODE=0` — disable V53 context policy and restore V52
  render-mode behavior, including the V51 depth selector.

All existing `TU_FRANE_*` safety and diagnostic controls remain available.

## Scope

V53 does **not** change Vulkan synchronization, GMEM allocation offsets, tile
packing, LRZ programming, shader code, barriers, WSI or command-buffer
correctness policy. The existing A810 GMEM safety classifier remains the final
authority after mode selection.

Treat V53 as an internal benchmark build until Crysis/Far Cry/Dirt/FC3 A/B
results confirm both performance and visual correctness.
