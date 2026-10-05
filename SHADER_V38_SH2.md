# Drnas Turnip A810 V38 SH2

Experimental Android ARM64 build based directly on confirmed SH1 commit
450a642c3f2e09a63511e264d37d0a59cd9ea60e and pinned Mesa
eda9aceb39d5ff169b096444abe366bdf2269e24. SH1 remains the device-tested baseline.
SH2 needs device testing; shader validation is not a GPU performance result.

## Changes

Two independent IR3 compiler experiments, enabled by default:

- Critical-path ordering: among legal instructions of the same existing CSR
  rank, below the SH1 pressure threshold, combine existing max-delay,
  nearest-consumer distance, and live-register growth. At or above the
  threshold, keep SH1 ordering. This uses the existing block-local pressure
  estimate, not measured GPU occupancy.
- SFU scheduling: replace the fixed outstanding SS-producer limit with a
  pressure-dependent cap. Default maximum is 6; effective limit decreases to
  4 at 20% estimated pressure, 3 at the SH1 threshold, and 2 at threshold+20.
  The upstream hard maximum of 8 remains. Legal dependency and synchronization
  checks stay in their existing paths.

Only compiler ordering, compiler options, cache identities and display name
change. V38 GMEM, LRZ, queue submission and texture window remain unchanged.
No floating-point precision or mathematical operation is changed.

The added score is constant work per existing ready candidate; it adds no
extra DAG traversal or shader-variant compilation in the driver. The original
scheduler's asymptotic complexity is unchanged.

## Controls

| Variable | Default | Meaning |
|---|---:|---|
| `TU_FRANE_SHADER_CRITICAL` | 1 | New critical-path tie-break; 0 disables it. |
| `TU_FRANE_SHADER_SFU` | 1 | New SFU limit; 0 restores the fixed limit 8. |
| `TU_FRANE_SHADER_SFU_WINDOW` | 6 | Maximum SFU limit, clamped to 2–8. |
| `TU_FRANE_SHADER_MODE` | 1 | Existing SH1 policy; 0 restores original V38 ordering and bypasses both SH2 experiments. |
| `TU_FRANE_SHADER_PRESSURE` | 35 | Existing SH1 pressure threshold, clamped to 20–80. |

Set both `TU_FRANE_SHADER_CRITICAL=0` and `TU_FRANE_SHADER_SFU=0` to restore
SH1 instruction scheduling inside this package. Restart the container after
changing compiler options. Each configuration has a separate cache identity
and needs a warm-up; do not compare its first cold run with a warmed run.

## Validation

The build requires policy boundary tests with UBSan, the inherited V38 checks,
and actual A810 IR3 compilation in a debug host build. Before applying SH2,
save 128 shader binaries from original V38 and SH1 across 64 compute/fragment
cases. After SH2, require exact byte equality for both fallback configurations,
compile each new experiment separately and together, and require deterministic
repeat compilation. Record register counts, estimated wave capacity, NOPs,
SS/SY bits and load/store instructions. Compile the Android AArch64 shared
library only after these tests pass.

Device comparison: same DXVK, FEX, resolution, game settings, cooling and
performance-mode choice as SH1. Run three Crysis passes, then Dirt 3 or the
same Far Cry 3 scene. Compare warmed averages, visible smoothness and artifacts.
No gain is claimed until those device comparisons are available.
