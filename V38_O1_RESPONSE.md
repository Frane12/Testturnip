# Drnas Turnip A810 V38 O1-RESPONSE

Internal experimental draft based directly on **V38 SH1**, the current fluidity
reference. Mesa base and all V38/SH1 render/shader decisions stay unchanged.

## Goal

This build does not chase a higher peak FPS by making the GPU more aggressive.
It attacks **driver work and response latency**: repeated CPU work that can be
eliminated without changing the selected render result.

## O1 changes

### 1. Carried GMEM DFS capacity

V38's bounded GMEM branch-and-bound search used
`frane_gmem_search_pixels()` at every visited node. That helper itself performs
a binary search and scans the current track list.

For an existing-track branch, however, V38 only changes the track's lifetime
`busy` mask. The track `cpp` values and track count do not change, so the exact
GMEM pixel capacity cannot change.

O1 carries the already-known capacity through those branches. Capacity is
recomputed only when a **new track** changes the cpp/track-count state.

- Search order: unchanged.
- Node budget: unchanged.
- Accepted layout criterion: unchanged.
- Result: intended to be policy-equivalent.
- Per reuse-node capacity bound: reduced from a track scan + binary search to a
  scalar compare.

The bounded search is still not magically O(n) in the formal worst case; V38
still caps the combinatorial search to 1024 nodes. O1 removes a repeated inner
cost from the common reuse edges instead of pretending the whole packing
problem became linear.

### 2. Two-choice hot render-pass cache

HOTPATH-V2 already gives A810 a 64-slot no-replacement cache that avoids the
shared mutex, unordered-map lookup, refcount traffic and timestamp update on a
hot hit.

Its weakness is direct mapping: two recurring render-pass hashes with the same
low six bits fight for one slot, even if the other 63 slots are empty.

O1 keeps the first lookup exactly as before. Only after a first-slot miss it
mixes the 64-bit hash and checks one alternate slot. Publication is still
no-replacement and permanently pinned, preserving the existing lifetime model.

- First-slot hit: same O(1) path as V38.
- First-slot miss: at most one extra O(1) probe.
- Map/mutex fallback: unchanged after both probes miss.
- Cache size: still 64 entries.
- A/B: `TU_FRANE_HOT2=0` restores the original direct-mapped behavior.

## Deliberately unchanged

- V38 SH1 shader-order policy and `TU_FRANE_SHADER_MODE`.
- IR3 generated instruction semantics.
- GMEM/SYSMEM selection policy.
- LRZ, barriers, cache flushes and synchronization.
- KGSL PWR_MAX request/refresh policy.
- GPU clocks, thermal control and kernel scheduling.

That scope is intentional: if this build feels smoother, the signal points to
CPU-side driver overhead rather than a hidden GPU policy change.

## Test order

Use the same Winlator/FEX/DXVK/resolution and the same thermal setup as the V38
SH1 reference.

1. Far Cry 3 High: camera pan and a combat section.
2. Crysis: three consecutive TimeDemo passes.
3. Dirt 3: two or three warm runs.
4. If O1 differs, set `TU_FRANE_HOT2=0` and relaunch to isolate the hot-cache
   change from the GMEM carried-capacity change.

Record average FPS, visible frame pacing, first-scene/level-transition stutter
and render correctness. This draft is specifically more interested in
**response and frametime consistency** than in a +1 FPS headline.
