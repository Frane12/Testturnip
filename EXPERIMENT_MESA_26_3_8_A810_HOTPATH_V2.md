# Frane Mesa 26.3.8 A810 HOTPATH-V2 EXP

Experimental A810 build layered directly on the verified 26.3.7 CORE-FASTPATH result.

## What changed

26.3.7 proved that repeated render-pass history lookup/bookkeeping was a meaningful CPU-side cost on the tested A810 workload. This build keeps the same rendering decisions and attacks the remaining bookkeeping on the already-safe hot path:

- increases the pinned direct render-pass history cache from 16 to 64 slots;
- hot-cache hits now use a borrowed history handle backed by the cache's permanent pin;
- borrowed hot hits do not increment/decrement the history refcount;
- borrowed hot hits do not update the per-use timestamp;
- ordinary misses, creation, fallback map lookups and every non-hot history retain Mesa's normal owning/refcounted behavior.

The publication ordering from 26.3.7 is preserved: a permanent ref is taken before pointer publication, the pinned bit is published before the matching hash, and a hot hit requires the matching hash before borrowing the lifetime.

## Deliberately unchanged

- 26.3.5 shader / pipeline / bounded RAM NIR cache path;
- 26.3.6 audit fixes;
- 26.3.4 GMEM runtime logic and PROFILED decision policy;
- sync / KGSL changes;
- WSI present behavior;
- rendering state and shader generation.

## Test goal

Use the same Far Cry 3 area and settings as 26.3.7. Compare:

1. gameplay FPS;
2. frametime stability;
3. menu vs gameplay FPS;
4. RAM after several minutes;
5. any new artifact, hang, or instability.

26.3.7 remains the known-good baseline if this experiment does not improve real hardware.
