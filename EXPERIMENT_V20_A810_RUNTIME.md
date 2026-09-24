# V20 A810 GMEM runtime experiment

Base: V19 IMapper5 `7c5cb2f78d86d8a6a3f4ab22638dec705537eb3d`.
Mesa is still pinned to 26.2.3. Experimental, not a demonstrated GPU fault fix.

## What changes

- A810-only default bandwidth policy uses Mesa's **selected actual tile grid**,
  not framebuffer area divided by a theoretical FULL-layout capacity. It checks
  tile area against that selected layout's gmem_pixels, physical/usable GMEM,
  binning availability, and limits this experiment to single-layer/view passes.
- Whole framebuffer tile count is a conservative upper bound for partial render
  areas. All attachment placement, alignment, cache reservations and load/store
  commands remain Mesa's responsibility. No physical GMEM size is falsified.
- Healthy memory: at most 32 tiles in profile 1 (48 in explicit profile 2).
  Caution: at most 18. Pressure: optional GMEM stops. Existing RAM thresholds stay.
- Retains full estimated attachment traffic. Allows equal per-pixel load/store
  costs when repeated draws make the **total** estimate profitable. Compact passes
  can enter with six draws. Tile and no-binning penalties still apply.
- Reuses existing RP timestamp commands and fence-completed results. A small
  atomic state per existing history records ticks normalized to 64 draws. Timing
  histories additionally distinguish tile shape, render area, draw and byte-cost
  buckets. No GPU wait, extra thread or secondary history map is added.
- Four SYSMEM observations warm up the baseline. Initial GMEM probes are at most
  one in eight cost-eligible decisions until three GMEM observations exist. Then
  require a 5% timing advantage; refresh SYSMEM every 64 eligible decisions.
  Losing GMEM gets only one retry in 128 eligible decisions. These are decision
  intervals, not frames; reused command buffers can reuse their recorded choice.
- Bandwidth mode avoids allocating per-tile timestamp slots when TS_TILE is off.
  RP timestamps fit existing RP data. This reduces autotune metadata, not game
  texture allocations. Existing BO/fence ownership is unchanged.

## Controls and comparison

Default V20: IMapper5 and the new A810 runtime policy enabled.

| Variable | Effect after restart |
| --- | --- |
| `TU_A810_GMEM_RUNTIME=0` | Restore V19's A810 selection and sampling allocation |
| `TU_FRANE_AIMAPPER=0` | Disable the new display backend independently |
| `TU_A830_SMART_GMEM_LOG=1` | Existing diagnostic switch; now also logs V20 actual tiles, physical/usable bytes and timing snapshots |
| `TU_DEBUG=sysmem` | Strict SYSMEM diagnostic override |

For an initial comparison remove explicit `TU_AUTOTUNE_ALGO`, `TU_DEBUG=gmem`,
`TU_AUTOTUNE_FLAGS=big_gmem` and `TU_A810_GMEM_BURST=1`. Explicit profiled/preferred
algorithms and special upstream required render modes retain precedence over the
new bandwidth policy. Depth diagnostics retain the V18 opt-in defaults.

Compare V19 and V20 in the same scene, first for image correctness, then frame
time, device temperature/power and RAM over 15 minutes. A nonzero GMEM timing
sample count confirms that eligible GMEM passes actually ran; build success and
an FPS screenshot alone cannot establish this.

## Validation and limits

The host C++ test exercises warmup, probe rates, slower-mode cooldown, recovery,
normalization, invalid timings, memory-tier limits and concurrent atomic updates.
CI compiles the real Android ARM64 driver and packages its applied source diff.
Neither test simulates the Adreno GPU. Probing GMEM can still expose an existing
rendering bug or device fault; this policy cannot detect image corruption or
recover transparently from VK_ERROR_DEVICE_LOST. Timing includes scheduling noise,
and workload buckets do not fully identify shader or clock changes.

Credit: Mesa/Freedreno/Turnip, DiskDVD-derived V18 shader workaround,
WinNative MIT IMapper backend, and Frane's experiments/testing.
