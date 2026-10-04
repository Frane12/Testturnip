# A810 S1.2 — GMEM planning

Internal draft built from S1.1 + V38 fusion, pinned Mesa eda9aceb39d5ff169b096444abe366bdf2269e24.

## Changes

- Exact best+1 feasibility replaces binary capacity searches at partial V38 nodes. Full capacity is still computed for winning leaves. Branch order, node budget and strict-win rule stay identical.
- Eight pointer-free GMEM plans per thread cache both improvements and no-win searches. Exact comparison covers item cpp/lifetime masks, seed tracks, GMEM capacity/alignment, block shift, search budget and pressure mode. Hash collisions are misses; attachment slots are reconstructed from current objects. No device or render-pass pointers survive in the cache.
- Immutable search budgets are read once per process. Cache uses approximately 7 KiB per participating thread, has a fixed bound and requires no mutex or shared atomic ticket.
- Independent application threads can construct passes concurrently with private caches. No extra worker pool was introduced: the small bounded search stays on the calling thread. This is removal of contention and repeated work, not newly asynchronous shader compilation or GPU execution.

These changes optimize render-pass construction and GMEM planning. The per-pass GMEM/SYSMEM Smart selector retains S1.1's early authoritative decision, fresh-pair learning, scene-reversal behavior and loss-budget cadence. Plans never cache a GMEM/SYSMEM decision or GPU address. Final layout admission and A810 GMEM safety remain authoritative.

## Defaults and comparison

No variables required. Smart, loss-budget, V38 search and the new planning path are ON. V39 future pressure remains OFF.

- `TU_FRANE_GMEM_PLAN=0`: disable the new pruning/cache path for direct S1.1 allocator comparison.
- `TU_FRANE_SMART=0`: existing Smart-layer control.
- `TU_FRANE_SMART_BUDGET=0`: existing loss-budget control.
- `TU_A810_26338_GMEM_SEARCH=0`: existing bounded-search control.
- `TU_FRANE_GMEM_PRESSURE=1`: opt-in V39; cache remains exact, V39 pruning stays inherited.
- `TU_FRANE_PROFILE_ID` is not required.

## Validation

Tests compile the actual old/new C++ allocator helpers extracted from source, rather than reimplementing the search in a model. Each run checks 28,000 randomized passes, identical cold/hit output, no search on exact cache hits, capacity/alignment invalidation, attachment-slot remapping, separate stencil mapping, legal lifetime overlap and 140,000 exact threshold comparisons. Four independent host threads exercise cache ownership. ASan/UBSan, disabled-path comparison and opt-in V39 checks run in CI alongside the inherited 716,040 policy boundary checks and loss-budget reversal tests.

An optimized host fixture of 20,000 repeated render-pass constructions measured 31.842 ms for the old allocator and 7.960 ms for the new path. This is one synthetic CPU workload, sensitive to compiler and host; it does not predict game FPS. Benefit is expected primarily when render-pass patterns are created repeatedly; persistent passes already amortize creation.

The workflow applies the full patch to pristine pinned Mesa, builds Android ARM64 using NDK r29, verifies driver ZIP/ELF/identity and creates only a DRAFT release. On-device FPS, Vulkan CTS and Android multi-thread stress have not been measured.

Compare whole warm runs with DXVK 1.9.4: Crysis three passes, Dirt 3 two or three runs, and longer Far Cry 2/3 gameplay. Compare default and `TU_FRANE_GMEM_PLAN=0` under the same setup.
