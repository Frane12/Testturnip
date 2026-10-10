# Turnip-Drnas A830 S2-RFC2 — Measured Render Profiler (PRIVATE DRAFT)

Base: **A830 BW2 Tile Cost + RFC1 one-shot scoring**. No BW3, CX1,
QP1 or IR3-LS1. The existing PROFILED learner, SMART priority, BW2 rollback,
GMEM allocation/correctness and timestamp GPU queries remain untouched.

## New opt-in native CSV
In Winlator environment variables add:

`TU_FRANE_A830_RFC2_TRACE_PATH=/storage/emulated/0/Download/turnip_a830_rfc2.csv`

Restart the Winlator container (not only the game). After running Crysis with
Vulkan, Android's Download folder may contain `turnip_a830_rfc2.csv`.

**Do not set** `TU_FRANE_A830_TRACE_PATH` (the old RFC1 path) at the same
time, unless specifically comparing logs; that would duplicate I/O.
Shared Android storage access depends on Winlator permissions. A writable
alternative such as `/tmp/turnip_a830_rfc2.csv` may work but live only
inside the Wine/Winlator Linux/container namespace.

Without `TU_FRANE_A830_RFC2_TRACE_PATH`, RFC2 executes no file I/O.

### CSV schema
Each row is one of:
- `DECISION`: exact history rp_hash, occurrence counter, quantized
  context signature, selected GMEM/SYSMEM mode, whether a timestamp
  measurement was requested, and reason class. Reason enum captures the
  *actual overriding selector* (SMART_V2, SMART_GMEM, ADAPTIVE,
  BW2_ROLLBACK, PROFILED, PROFILED_LOCKED, or RUNTIME). Feature values,
  BW2 score and tail-history strength are included for diagnosis.
- `TIMING`: **completed GPU timestamp duration** (`gpu_ns`, nanoseconds)
  from the existing `rp_entry::get_rp_duration()` in the
  submit-thread `rp_history::update()` path. Also records current
  GMEM/SYSMEM moving averages in ns, their sample counts and updated
  tail-confidence. No extra GPU timestamp queries/fences are created.

Use `(rp_hash, occurrence)` to associate measured TIMING entries with
a DECISION entry when both were sampled. For TIMING-only rows, the mode
and RP identity are still known, but no features are reconstructed.

Diagnostic sampling is bounded: per-history decision events at 1/64
occurrences, or every 16th occurrence when a measurement is requested;
GPU timestamp events every 8th measured occurrence; max 8192 emitted rows
per process, after which the trace stops. Some measurements may be
unmatched to decisions because of sparse sampling. Never interpret
the CSV as a complete capture or assume zero ns on DECISION means
an instantaneous GPU render.

## Device testing
1. Run Crysis Vulkan benchmark 3 times **without RFC2_TRACE_PATH** to check
   whether RFC2 affects performance. Max Frame Latency unchanged.
2. Restart container with RFC2_TRACE_PATH, run the benchmark again and
   upload the .csv for offline analysis; diagnostic logging costs CPU/I/O.
3. If no file appears, inspect Android storage permissions, process env
   propagation and Linux logcat for `A830 RFC2: cannot open`. Host
   CSV tests alone cannot prove permissions in Winlator.
4. Do not use log-on FPS as performance comparison against log-off runs.

Scope is intentionally diagnostic. Do not force GMEM for render-pass
families with `sys_cpp=0` or negative measured tail history merely
because the structural cost model cannot evaluate them.
