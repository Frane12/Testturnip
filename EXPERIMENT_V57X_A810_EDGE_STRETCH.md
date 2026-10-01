# Drnas Turnip V57X — EDGE-STRETCH

**Adreno 810 · experimental branch based directly on V57 PROFILED-TAIL-GUARD**

V57X is intentionally not a continuation of the V58–V68 learner experiments.
It returns to the V57 reference stack and changes only the outer boundary of
the V57 tail decision.

## Stable base kept intact

The build retains the pieces that already earned their place in the reference
stack:

- **V47/V45 concurrent-binning keep policy** — the repeatable heavy-pass
  baseline remains unchanged.
- **V53 bounded depth window** — the proven 16..23 draw primary depth band is
  retained.
- **V56 GMEM hard-push** — measured winners and the stronger cold-start GMEM
  prior remain intact.
- **V57 PROFILED tail guard** — still the baseline decision and exact fallback.

No V58+ learner, scan, signature, regime-hold or shader/resolve experiments are
pulled into this branch.

## New experiment: stretch both edges, not the middle

V57X adds one short control:

`TU_FRANE_EDGE=0` — exact V57 behavior.

`TU_FRANE_EDGE=1` — add only the **hard-tail floor guard**.

`TU_FRANE_EDGE=2` — floor guard plus **bounded headroom reopening**.
This is the default.

### Floor guard

At the extreme replay tail, V57X asks for stronger evidence before allowing an
old GMEM win to overrule the structural risk.

The hard-tail class is deliberately narrow:

- depth/stencil load-store, at least 8 estimated tiles and replay work >= 320;
  or
- >=1080p pass, at least 8 tiles and replay work >= 256.

Inside that class, V56 is preserved only when the evidence is dominant:

- GMEM attachment bandwidth <= 1/2 of SYSMEM; or
- measured state armed with score >= 8 and live SYSMEM probability <= 15%.

Otherwise V57X does **not** force SYSMEM. It simply gives the pass back to Mesa
PROFILED.

### Headroom reopening

V57's normal tail guard can defer medium-cost Z/S passes that are structurally
ambiguous. V57X mode 2 reopens only a bounded part of that band:

- Z/S load-store;
- 4..6 estimated tiles;
- replay work 128..224;
- and either:
  - GMEM bandwidth <= 4/5 of SYSMEM, or
  - measured score >= 6 with live SYSMEM probability <= 38%.

This is the deliberate performance risk in the build. It keeps V56 active in a
small medium-tail region where the evidence still leans toward GMEM, while the
new hard-tail rule protects the far end.

The existing final A810 GMEM safety classifier remains authoritative.

## Why this shape

The goal is to probe both ends of a stable driver without replacing the stable
driver:

- push the **top** by reclaiming a small evidence-backed medium-tail GMEM band;
- protect the **bottom** by making the extreme replay tail harder to override;
- leave the large middle of V57 untouched.

That makes an A/B result interpretable.

## Suggested first test

Use normal defaults first: no variables required (`TU_FRANE_EDGE=2`).

For a clean same-binary comparison:

1. `TU_FRANE_EDGE=0` — exact V57 selector.
2. `TU_FRANE_EDGE=1` — floor guard only.
3. `TU_FRANE_EDGE=2` — full V57X.

Keep the rest of the container identical. For the controlled DXVK reference,
use the established baseline rather than changing DXVK during the driver A/B.

The useful signal is not only average FPS: record minimum/1% low, repeated warm
passes, visible stutter, RAM behavior and any artifact change across Crysis,
Dirt 3, Far Cry 2/3 and the other games already used in the broad matrix.

## Scope

V57X does not change GMEM allocation/offsets, render attachment programming,
LRZ, barriers, shaders, MSAA/resolve admission, WSI or Vulkan synchronization.
It is a selector-boundary experiment on top of V57, not a rewrite.
