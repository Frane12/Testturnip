# Frane Mesa 26.3.2 A810 TURBO EXP

**Experimental downstream name, not an official Mesa release.**

Baseline: the green **Frane Mesa 26.3.1 EXP** build, itself based on pinned
Mesa `26.3.0-devel` commit `eeca16aa41e89a114e53e76439df623c7efb9519`.

This branch deliberately leaves the favorite 26.3.1 build untouched. It is an
A810 performance experiment layered on top of all 26.3.1 sync/hang fixes.

Changes:

- A810 clear-winner PROFILED sampling base goes from 1/8 to 1/16. V29 still
  forces dense <=1/2 measurement for cache-warmed or close/uncertain modes.
- Autotune cleanup/reaper housekeeping goes from every 32 submits to every 128.
- Accepted A810 PWR_MAX is refreshed every 1024 successful submits instead of
  every 256.
- Infinite KGSL waits avoid unnecessary monotonic-clock reads.
- WAIT_ANY initial state classification is one pass instead of three.
- Poll storage is sized to the wait set up front to avoid growth/reallocation.
- FD-only WAIT_ANY no longer attempts `timestamp_to_fd(NULL, 0)`.
- All Mesa 26.3.1 EXP WAIT_ANY semantics, timeout saturation and submit-mutex
  correctness fixes remain in place.

No new GMEM layout, shader, descriptor-prefetch, WSI present-mode or neural/AI
changes are introduced here.
