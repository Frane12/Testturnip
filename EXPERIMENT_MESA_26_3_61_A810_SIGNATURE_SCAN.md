# Drnas Turnip V61 — SIGNATURE-GATED SCAN

Internal A810 experiment layered strictly on V60 FREQUENCY-AWARE-SCAN.

## Why V61 exists

V60 fixed the largest conceptual problem in V59: one universal scan budget was
wrong for both rare and per-frame render passes. The latest Crysis run was much
more repeatable in the warm passes, but the deterministic minimum still landed
around the early tail hotspot.

The code audit found a remaining mismatch between V60 and V58:

- V60 cold/rare histories still force up to one measured sample per mode.
- V58 cannot become actionable until it has six paired GMEM/SYSMEM samples.

For a truly rare pass, the 1+1 forced probes can therefore hurt one benchmark
frame while never producing enough evidence for the learner to make a decision.

V61 removes that dead-cost path.

## Policy

V61 keeps the exact V57 structural tail-risk classifier, V58 learner, V59
bounded scan and V60 frequency scan as fallbacks.

The new default policy uses recurrence plus a compact structural signature made
from:

- estimated tile count;
- replay work (tiles × draw calls);
- draw-call bucket;
- render-target pixel bucket;
- depth/stencil load-store participation.

The signature does **not** merge Mesa render-pass histories or replace Mesa's
exact RP key. That is deliberate: upstream includes image identity in the RP
key to avoid false matches, so V61 uses structure only to decide how much
evidence is required before forcing exploration.

## Scan as rescue, not cold exploration

A cold/rare history gets no forced V61 scan. It remains on Mesa PROFILED and can
collect natural timing samples.

For a moderate-cost signature the base recurrence threshold is 128. More
expensive signatures require 192 or 256 occurrences because a wrong loser probe
is itself more costly.

Natural V58 evidence lowers the wait:

- 4+ paired samples: activation at 1× the signature threshold;
- 2–3 paired samples: 2×;
- 0–1 paired samples: 4×.

When rescue activates, V61 fills only to the six-pair V58 readiness threshold.
If V58 is already ready and confidence reaches 4, scanning stops completely.
Only very hot but still inconclusive histories may extend to 8 or 10 samples
per mode.

Hostile probes that contradict an extreme PROFILED probability are throttled
more aggressively for expensive signatures.

## Safety / audit notes

The new policy is a pure header-only selector. It has:

- no dynamic allocation;
- no mutexes, waits or blocking calls;
- no unbounded loops;
- saturating recurrence-threshold multiplication;
- bounded shift counts for probe masks;
- no changes to GMEM layout/offsets, attachments, LRZ, barriers, shaders,
  concurrent binning, WSI, MSAA/resolve or Vulkan synchronization.

The pinned Mesa PROFILED implementation already uses a slow + fast adaptive EMA.
V58 additionally keeps a fast-rise/slow-decay tail envelope. V61 therefore does
not add a third duplicate timing filter; it gates when forced evidence is worth
collecting.

## A/B

No variables are required for the first test.

- `TU_FRANE_SIG=1` — V61 signature-gated rescue scan (default)
- `TU_FRANE_SIG=0` — exact V60 recurrence-aware scan
- `TU_FRANE_FREQ=0` — exact V59 fixed-target scan
- `TU_FRANE_SCAN=0` — exact V58 selector behavior

## Crysis target

Use the same three-pass CryEngine 2 GPU TimeDemo.

The first thing to watch is the minimum around the previous frame ~150–160
hotspot. The desired result is to keep V60's tight Run 1/Run 2 repeatability
while removing the cold/rare forced-probe penalty. Warm average should remain in
the same band or improve once truly hot passes accumulate enough natural or
rescued evidence.
