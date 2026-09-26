# Frane Mesa 26.3.4 A810 GMEM-RUNTIME EXP

**Experimental downstream name, not an official Mesa release.**

Baseline: green **Frane Mesa 26.3.3 A810 PROFILE-TURBO EXP**.

The 26.3.3 PROFILED learner and `TU_FRANE_PROFILE_ID=<game>` cache remain the
primary decision system. The new runtime does **not** restore the older A810
custom BANDWIDTH algorithm and does not change GMEM allocation, attachment
offsets, tile dimensions, cache registers or BO ownership.

Runtime behavior:

- Default ON for A810 in this experimental build.
- Optional rollback: `TU_A810_GMEM_RUNTIME=0`.
- No additional variable is required for normal testing; keep only the existing
  `TU_FRANE_PROFILE_ID=<game>` if desired.
- Both SYSMEM and GMEM must have at least 8 measured samples before the runtime
  can arm.
- Strong GMEM wins add confidence; marginal/no wins decay it.
- Hysteresis: arm at score 6/8, disarm at 2/8.
- When armed, layout-sane and PROFILED already leans to GMEM
  (SYSMEM probability <= 40), runtime promotes GMEM for 63/64 decisions.
- Every ~64th decision is a forced, measured SYSMEM control probe so scene
  changes can update the averages and disarm the runtime.
- If physical/usable GMEM metadata, FULL-layout pixels, draw count, pass size or
  estimated tile count fail the conservative guard, runtime makes **no override**
  and 26.3.3 behavior remains unchanged.

Internal validation before the Android build:

- deterministic boundary/unit test under ASan+UBSan;
- the same deterministic policy under optimized O3+UBSan;
- randomized stress/property test over zero, ordinary and UINT64_MAX-scale
  values;
- multiple independent stress seeds;
- state-machine hysteresis/no-thrash checks;
- source assertions that PROFILED remains primary and the old A810 BANDWIDTH
  runtime stays disabled.
