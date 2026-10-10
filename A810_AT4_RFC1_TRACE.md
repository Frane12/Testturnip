# A810 AT4-RFC1 diagnostic draft (no public release)

Derived strictly from the last A810 AT4 S1Guard draft branch, pinned Mesa
**26.3.0-devel** at `eda9aceb39d5ff169b096444abe366bdf2269e24`.
The original AT4 full patch remains unchanged; this RFC adds only one
header and instrumentation in `tu_autotune.cc`, plus driverInfo.
Any anchor/source drift aborts the build. No GMEM, render policy, shaders,
timestamps, scheduling, or autotuner heuristics are changed.

## Collecting data
In the Winlator/container environment, set:

```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_AT4=1
TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/turnip_a810_at4_rfc1.csv
```

Choose an **absolute, writable path visible to the emulator app**.
Some Android/container installs cannot write directly to Download: then
use the application's accessible private storage folder. Check that the
file actually appears. The logger cannot create missing parent folders.
If the file does not appear, stderr/logcat prints one open error.

If the path variable is absent: **no CSV, file I/O, or trace atomic RMW**.
The trace is for diagnostic runs only: even sampled file I/O perturbs CPU
timing somewhat. Use a fresh filename for each test.

## What is logged

- `DECISION`: original render-pass hash, occurrence, AT signature (when
  a measured RP entry exists), actual final mode after depth-frontier
  and correctness gate, selected source, PROFILED probability, whether
  profiling was requested, context eligibility, render pixels, selected
  tile count, drawcalls, per-pixel estimated bandwidth and available GMEM.
- `TIMING`: GPU duration in nanoseconds from Mesa's **existing**
  per-render-pass timestamp result, with mode-specific GPU time
  exponential moving averages and sample counts. No extra GPU query.
- Source values: `AT4_OVERRIDE`, `AT3_CONTEXT`, `DEPTH_FRONTIER`,
  `GMEM_SAFETY`, or `PROFILED_OR_S1`. The latter is intentionally
  ambiguous rather than claiming to have proved an S1 override.
- Join a `TIMING` with its sampled `DECISION` by
  `rp_hash + occurrence` (and signature if present). Do not mistake
  render-pass GPU time for total frame time. Reused RP entries can have
  multiple TIMING observations for one decision.
- To keep logs bounded, records cover the first four instances of an
  RP, every 64th decision, and every 16th profiled decision/timing sample.
  The logger writes at most 8192 CSV rows per process.

## Benchmark recommendation

Run 3 warm benchmarks with fixed device temperature and identical
resolution. Compare CSV distributions of GPU time for paired
SYSMEM/GMEM render passes, selection flip rate, presence of AT4
overrides, correct-safety fallback rate, and actual FPS/frame pacing
from an independent FPS overlay. Keep Max Frame Latency enabled for
comparability with earlier A810 results.

This is an experimental **draft**, not a public release. Static host
tests, source-drift guards, a real aarch64 KGSL build and ELF checks are
required by the draft workflow.
