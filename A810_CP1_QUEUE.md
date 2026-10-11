# Turnip-Drnas A810 CP1 — Queue Submit Diagnostics (PRIVATE DRAFT)

Based on the A810 AT7 image derived from the user's tested AT6.3
EarlyWinner source. **GMEM/SYSMEM selection, AT4/AT63/AT7 thresholds,
GPU timestamp queries, shader compilation, render layouts and LRZ safety
are unchanged**.

## A810 CPU command-submission work
- Skip a zero-length command-buffer entry batch before it reaches the
  KGSL/DRM `util_dynarray_grow(..., 0)` path. This cannot remove any
  actual IB commands. It is explicitly restricted to A810.
- For exact A/B, `TU_FRANE_CP1_ZERO_SKIP=0` restores the prior path.
  Default is `1`; the FPS benefit is **not yet proven**.
- Optional diagnostic CSV samples first 16 and every 16th subsequent
  queue submission, recording CPU **nanoseconds** spent in:
  mutex wait, command-buffer/patchpoint setup, command gathering,
  autotuner submit processing, pre-kernel bookkeeping, kernel submit and
  after-kernel work. It does *not* add GPU queries or change GPU policy.
- No CPU clock is read and no CSV I/O occurs unless a valid absolute trace
  path is explicitly configured. CSV I/O occurs outside submit_mutex.

## Variables

Without logging (first benchmark):
```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_AT7=0
TU_FRANE_CP1_ZERO_SKIP=1
```

The AT7=0 setting is deliberate, to compare with the AT6.3 baseline the
user is currently testing. Use `TU_FRANE_CP1_ZERO_SKIP=0` to disable CP1
in the *same binary*. Restart the emulator container after changes.

For one short diagnostic run only, add:
```ini
TU_FRANE_A810_CP1_TRACE_PATH=/sdcard/Download/a810_cp1_submit.csv
```
The path must be writable from the emulator process. If not, choose an
application-private path. Logging perturbs CPU scheduling, so do not use
CSV-logged FPS as a speed claim. GPU AT4/RFC1 telemetry remains separately
optional via `TU_FRANE_A810_RFC1_TRACE_PATH` and should normally be unset.

## Measurement plan and limits

Compare warm runs in ABBA order using same resolution/FEX/DXVK/Max Frame
Latency/temperature. For AT6.3 the user's best prior sample is three warm
Crysis runs of 35.96 / 36.26 / 36.24 FPS (mean 36.15 FPS). A tiny
optimization may make no measurable FPS difference.

If CP1 does not reproducibly improve FPS beyond ~1% against the same
binary's CP1-off control, **do not over-optimize it**. Use the new CSV to
identify genuine CPU overhead (e.g. mutex wait vs. kernel ioctl vs.
patchpoints) and separately investigate that dominant phase. If kernel
submission is already negligible compared to 27.6 ms GPU frame time,
move to other bottlenecks.

This is a draft for A810 only; device performance and Vulkan correctness
are not yet validated.
