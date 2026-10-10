# A830 RFC1 — Render Feature Cache & opt-in CSV trace (private draft)

**Base:** tested A830 S2-BW2 Adaptive Tile Cost, not BW3, CX1, QP1 or
IR3-LS1. Mesa allocator, LRZ, barrier, subpass, GMEM safety and existing
PROFILED/tail learner are unchanged.

## Performance-oriented change
On the normal PROFILED runtime path, SMART and the A830 adaptive rollback
can both evaluate BW2 Tile Cost with identical selected tile geometry and
snapshot history. RFC1 calculates BW2 **once per decision** after the existing
early-return gates, and passes its immutable result into both consumers.
This avoids a duplicate expensive quotient/ratio evaluation, and cannot
reuse results across render passes or stale history updates.

- `TU_FRANE_A830_RFC1=1`: enable this single-decision evaluation reuse
  (default, A830 only).
- `TU_FRANE_A830_RFC1=0`: identical BW2 evaluation paths and decisions.
- No new persistent map or guessed bucket-history that could contaminate
  timing decisions. The original rp_key remains the sole history identity.

## Optional CSV file from native Turnip driver
Set the environment variable before Winlator starts:

`TU_FRANE_A830_TRACE_PATH=/storage/emulated/0/Download/turnip_a830_rfc1.csv`

This is an **absolute Android/Linux path**, not a Windows `C:\` path.
If Winlator has permission for shared Downloads, a normal Android file
manager should be able to see the CSV at:

`Internal storage/Download/turnip_a830_rfc1.csv`

**Permission warning:** Android scoped storage and some Winlator variants
block native writes to shared Downloads. No file means this path was NOT
writable or the instrumented PROFILED path was never visited. In that
case try `TU_FRANE_A830_TRACE_PATH=/tmp/turnip_a830_rfc1.csv` to
test logging inside the Linux/container namespace (which might not be
directly visible to Android apps). Check Android logcat for
`A830 RFC1 trace: cannot open` if available. We deliberately do not
create directories or silently switch to another path.

**Zero file I/O when TRACE_PATH is absent.** With a path supplied, the
driver samples up to 2048 entries, one per 64 occurrences for each
render-pass history, writes a CSV header and immediately closes the file.
A line contains the exact render-pass history ID, grouped structural
fingerprint, tile geometry, draw counts, bandwidth/attachment footprint,
tail history snapshot, BW2 score and the **actual final GMEM/SYSMEM mode**.

This CSV does not yet provide the actual GPU timings for each event:
the per-RP measured learner separately owns and updates those. The CSV
does *not* contain shaders, memory contents, file names or user data.

## How to test
1. Baseline benchmark with `TU_FRANE_A830_RFC1=1`, no TRACE_PATH.
2. Compare 3 Crysis runs with `TU_FRANE_A830_RFC1=0` in a restarted container.
3. Diagnostic test separately with TRACE_PATH enabled, then send the CSV.
4. Keep Max Frame Latency, DXVK, resolution, CPU affinity and other settings
   unchanged. Diagnostic mode has file I/O overhead; do not compare its FPS
   against a run without tracing.

Host source guards, regression tests and Android ARM64 compile are necessary
but do **not** establish successful file access on a user's particular device.
