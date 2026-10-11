# A825 S Ultimate v0.1 D1 — experimental test build

Android arm64 / KGSL driver for Adreno 825, built from Mesa 26.3.0-devel with the Ultimate adaptive render-pass policy.

- Correct A825 chip ID: `0x44030000`; Mesa fallback record: `0xffff44030000`.
- Dedicated two-slice, four-CCU cache profile; GMEM capacity comes from the kernel.
- Bounded recent GPU timing feedback, fresh paired winner votes and occasional GMEM/SYSMEM reassessment.
- A825 custom features are enabled by default. Native CSV logging is disabled by default.

**A825 hardware startup, rendering correctness and performance are not yet confirmed.** Android compilation and host lookup, allocator, feedback, concurrency and CSV tests passed. Please treat this as a test build; no FPS improvement is claimed.

## Test and report

Import the driver ZIP in your emulator, restart the process and run four benchmark passes without logging. Report the exact device, Android version, emulator, DXVK/VKD3D, game, resolution, settings, per-run FPS/playtime and any artifacts or crashes.

Optional diagnostic run only, with a native Android path writable by your emulator:

```text
TU_FRANE_A825_TRACE_PATH=/storage/emulated/0/Download/a825_ultimate.csv
```

Exit the game normally to flush the CSV. It records chip ID, raw GPU ID, slice/CCU count, mode, decision source and existing GPU timestamp ticks. Attachment bytes are modeled estimates, not measured DRAM bandwidth.

Restart after changing an option:

```text
TU_FRANE_A825_ULTIMATE=0
```

Disables the A825 custom policy while preserving device registration, cache layout and safety checks.

```text
TU_FRANE_A825_GMEM=0
```

Forces the guarded A825 path to SYSMEM for diagnosing GMEM artifacts.

Minimum Android API: 34. This release contains the exact previously built test ZIP, verified by SHA-256 before publishing.

Build provenance: Generated-by: LLM.

