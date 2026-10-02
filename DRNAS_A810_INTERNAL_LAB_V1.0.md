# Drnas Turnip A810 INTERNAL-LAB V1.0

This is an intentionally aggressive private A810 branch.

Base: **V59 LRZ-CLEAN**.

The objective is not immediate stability. The objective is to combine the most
promising independent mechanisms, deliberately overshoot the stable branch, and
see whether the A810 has a clearly higher throughput region worth stabilizing.

## Default stack

**LRZ**
- V58 no-Z-write LRZ validity retention.
- V59 non-sticky stencil LRZ write-disable.

**GMEM**
- V56 measured GMEM hard-push remains enabled.
- INTERNAL-LAB widens the armed winner frontier again:
  - measured challenge allowed deeper into nominal SYSMEM territory;
  - structural thresholds are lower;
  - control probes are less frequent for strong winners;
  - cold start can become almost pure GMEM when structure looks favorable.
- V57X `TU_FRANE_EDGE=2` is restored by default so medium-tail passes can
  reopen GMEM while hard tails still have the guard.

**IR3 shader scheduling**
- Based on the useful V66 broad-workload pressure controller.
- LAB ladder is intentionally wider than V66:
  - <10% live pressure -> window 8
  - <22% -> 6
  - <38% -> 4
  - <55% -> 3
  - >=55% -> 2
- `TU_FRANE_SHADER=0` restores the old scheduler behavior.
- The switch is included in Vulkan and IR3 disk-cache identities.

**Concurrent binning**
- V47 profiler infrastructure remains.
- Default changes from conservative V45 keep mode 1 to balanced mode 3.
- All normal Turnip CB correctness/synchronization gates remain intact.

**Resolve**
- `TU_FRANE_RESOLVE=1` opens only Mesa's existing simple color 2x/4x GMEM
  resolve path.
- Depth/stencil resolve, custom resolve, unresolve, feedback, multiview,
  conditional load/store, MSRTSS and 8x+ remain blocked.

## Deliberately not included

V67 MOMENTUM-SCHED is not revived. It was a measured negative result: strong
average FPS remained, but Dirt 3 minimums fell and Crysis gained a repeatable
hotspot. INTERNAL-LAB spends risk on mechanisms that have either worked before
or have a clean hardware rationale.

## First test

Run **with no extra variables**. Treat it as an overclocked policy build.

Useful first sweep:
1. Dirt 3 benchmark: two consecutive warm runs.
2. Far Cry 2 benchmark: three loops.
3. Crysis: standard three-pass run.
4. Far Cry 3 gameplay for at least several minutes.

Record average/minimum, visible smoothness, artifact/crash behavior and RAM.
If the branch shows a meaningful FPS jump, V1.1 should remove or soften one
aggressive module at a time until the gain survives with acceptable stability.
