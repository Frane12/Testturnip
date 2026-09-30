# Drnas Turnip V57 — PROFILED-TAIL-GUARD

## Why this experiment

V56 is retained as the base. In the Crysis 3-pass TimeDemo it improved the
warm average while the same minimum frame remained unchanged. That is a good
reason to protect the V56 win and target only expensive tail passes.

## Mesa/community audit

Mesa's PROFILED autotuner already has the right high-level behavior for a hard
case: measure both render modes, move probability gradually, and let repeated
timing evidence dominate. V57 therefore does not hard-force SYSMEM when it
detects a risky pass. It cancels the downstream SMART/TURBO override and hands
that pass back to Mesa PROFILED.

A current A810 community Freedreno/Gallium experiment also contains a useful
device-specific heuristic: prefer SYSMEM when A810 GMEM must replay multiple
tiles with depth/stencil load-store traffic, and for sufficiently large
multi-tile render targets. That code is Gallium, not Turnip, so V57 ports the
principle rather than copying the path.

## V57 policy

The guard fires only when V56 turbo is enabled and all of these line up:

- A810 V57 guard is enabled (TU_FRANE_TAIL=1, default).
- Depth/stencil load-store traffic is present.
- Estimated GMEM tile count is at least 4.
- estimated_tiles * drawcalls >= 128.

A secondary large-render-target rule requires at least 192 replay-work units at
1920x1080 or above.

Two vetoes preserve GMEM:

1. Mesa render-pass bandwidth accounting says GMEM traffic is <= 2/3 of SYSMEM
   traffic (a strong static GMEM win).
2. The existing measured A810 state is armed with score >= 7 and PROFILED's
   live SYSMEM probability is <= 30 (strong measured GMEM agreement).

When the guard fires the result is defer to Mesa PROFILED, not force SYSMEM.
That is the key difference from a blunt workaround.

## A/B

Default: TU_FRANE_TAIL=1

Exact V56 selector behavior: TU_FRANE_TAIL=0

For the first run, use no extra variables. Run the same three-pass Crysis
TimeDemo and compare especially the deterministic minimum around the prior tail
frame, while checking that the V56 warm average is retained.
