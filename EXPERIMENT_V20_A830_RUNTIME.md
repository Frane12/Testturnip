# Frane V20 A830 GMEM Runtime (experimental)

**Target:** exact known Adreno 830 IDs on Android/KGSL. Mesa 26.2.3 pinned
to `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`.
**Base:** A830 V18 Depth Diagnostic, retaining V16 KGSL, BO/refcount,
memory-pressure, lean-cache and image/UBWC safety experiments.
This is **not** an A810 binary renamed A830.

## What V20 changes

- Adds the MIT-licensed WinNative IMapper5 stable-C metadata backend from
  A810 V19 as optional Android display interoperability (not a GMEM fix).
- Uses Mesa's actual selected A830 GMEM tile layout and tile grid, including
  alignment and its own GMEM capacity, rather than the FULL-layout pixel
  approximation. Does not change tile register programming, attachment
  load/store/resolve, UBWC color path, or claim that GMEM is larger than it is.
- Keeps V15-K/L's conservative A830 modeled bandwidth/cost heuristics and
  V16 RAM fail-closed gates: at least 10 draws, observed bandwidth, full
  attachment traffic, >=12.5% estimated saving plus tile/tier penalties.
  Actual grid limits: max 12 tiles with healthy RAM, max 8 with caution,
  no optional GMEM under memory pressure.
- Only for eligible A830 bandwidth-autotuned render passes, records existing
  fence-completed RP GPU timestamps; 4 SYSMEM observations before probing;
  max 1/8 eligible GMEM decisions while gathering 3 GMEM samples. Thereafter
  requires >=5% measured speed gain, with SYSMEM rechecks every 64 eligible
  decisions or losing-GMEM retries every 128. Reuses existing per-renderpass
  history, with workload/tile key, and doesn't wait for the GPU on CPU.
- Skips unnecessary per-tile timestamp storage if only RP timestamps are
  needed. Neither an active texture nor an in-flight GPU buffer is
  prematurely freed.

## Winlator A/B variables (restart game/container after changes)

| Variable | Effect |
| --- | --- |
| *(unset)* | V20 runtime and IMapper5 enabled; A830 V18 depth A/B retained |
| `TU_A830_GMEM_RUNTIME=0` | Restore V18 A830 GMEM selection/sampling, retain V20 IMapper |
| `TU_FRANE_AIMAPPER=0` | Revert optional IMapper backend independently |
| `TU_A830_SAFE_DEPTH_UBWC=0` | Restore V16 A830 internal depth/stencil compression |
| `TU_A830_SMART_GMEM=0` | Disable Frane optional bandwidth policy |
| `TU_A830_SMART_GMEM_LOG=1` | Periodic 5-second mode, actual tiles, and timing counts |
| `TU_DEBUG=sysmem` | Explicit all-SYSMEM fallback for corruption/device faults |

Initially remove `TU_AUTOTUNE_ALGO`, `TU_DEBUG=gmem`,
`TU_AUTOTUNE_FLAGS=big_gmem`, and old A810-specific variables.
Do not infer GMEM success from the FPS overlay alone: check V20 logs for
GMEM timing count > 0. Then benchmark identical Far Cry 4 location/settings,
DXVK, resolution, FPS cap, 0/15/30-minute RAM, frame time, heat and image
correctness against A830 V18, SYSMEM fallback and the known-good driver.

## Limits

This is a controlled GPU-time selection experiment, **not** a proof that
A830 GMEM write-page faults or rectangular artifacts are fixed. The timing
history doesn't detect image corruption. Existing already-recorded CBs can
reuse an earlier decision; probes count eligible *decisions*, not frames.
A device-lost error requires restarting the app; capture KGSL fault type,
IOVA and driver log to determine the underlying fault. Host tests and
ARM64 compilation validate policy/build, not hardware correctness.

Credit: Frane12 experiments/testing; Mesa/Freedreno/Turnip, DiskDVD-derived
A830 V18 stack; WinNative MIT IMapper5 backend.
