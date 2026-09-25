# Frane Turnip V24 A810 — lean CPU hot-path experiment

**Exact base:** V23 A810 Lean WSI (V22 Lean Profiled on V18 sampled-depth),
Mesa 26.2.3 `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`.
V18, V22, V23, A830 branches are untouched. This is an **experimental**
CPU reduction, not a claim of increased FPS or a GPU/GMEM correctness fix.

## Audit of the DiskDVD workaround

The existing `IR3_A810_DISKDVD_PREFETCH` workaround sets
`IR3_DBG_NODESCPREFETCH` once in `ir3_compiler_create()` for exact A810
chip IDs. It disables a shader optimization globally, **not** a shader
prefetch command executed once per frame. Removing it, re-enabling it
selectively or editing its shader code without a reproducible correctness
test risks bringing back camera-relative depth/lighting artifacts.

V24 therefore deliberately does **not** modify the DiskDVD shader patch,
shader register allocation, prefetch policy, shader cache, descriptors,
UBWC, tiles, GMEM/SYSMEM estimation, KGSL fences, barriers or BO lifetime.
CI compares the completed IR3 and WSI source files byte-for-byte with V23.

## CPU work removed after V22 learning

1. Plain PROFILED may end at 0% or 100% after a permanent history lock.
   V22 still generates an xorshift RNG value and divides by 100 on every
   later renderpass even though both results choose the identical mode.
   V24 omits that unused random/modulo operation **only on A810,
   one-time command buffers, no preemption override, plain PROFILED,
   when the measured probability is already 0 or 100**. Uncertain decisions
   and PROFILED_IMM keep the original code and RNG behavior.
2. When a mode is uncertain or a losing-mode probe is selected,
   V22 always measures. V24 doesn't read the static sample-interval setting
   in those full-measurement cases, including warm-up. 95-99% confidence
   preferred-mode sampling retains V22's exact 1/N schedule and counters.
3. In `process_entries()`, V22 reads the mapped GPU autotune fence at
   every submission, including after it has skipped all measurement entries.
   V24 skips that **read** if the A810 completed-results queue is empty.
   When there are queued batches, the existing processing, fence ordering,
   refcounts and synchronization are unchanged. No GPU wait is removed.

## A/B test, exact controls

| Variable | Effect |
| --- | --- |
| `TU_A810_V24_FASTPATH` unset / `1` | Enable all three V24 CPU shortcuts |
| `TU_A810_V24_FASTPATH=0` | Restore V23 code paths (same V24 binary) |
| `TU_FRANE_PRESENT_MODE=off` | Disable optional V23 MAILBOX preference |
| `TU_AUTOTUNE_ALGO=profiled` | Use plain profiled; V24 shortcuts cannot optimize `profiled_imm` |
| `IR3_A810_DISKDVD_PREFETCH=0` | Existing shader workaround A/B; only test if image correctness can be inspected |

Compare V23 vs V24-with-flag-off vs V24-default at identical FC3
location/medium-high-texture settings, FEX 2609, Sarek async 1.10.8,
resolution, affinity, cooling and power state. Keep the original V18
working driver for recovery. Measure warm-up separately from 30-minute
steady state; a permanently locked probability requires enough successful
samples and consistency, so some games may never trigger shortcut #1.

## CI safety checks

- Host C++/UBSan unit tests for 101 probability values × 1000 pseudo RNG
  outcomes × five sample intervals, asserting V23 and V24 **mode and
  measurement equivalence**; V22 and V23 regression tests remain.
- Source assertions: unchanged V18 probability updater, DiskDVD IR3 source
  and V23 WSI source after the V24 patch.
- Pinned Mesa, fail-closed patch anchors, Android ARM64 KGSL cross compile,
  AdrenoTools ZIP format/ELF checks, `mesa-applied.patch` and checksums.

**Limits:** No device benchmark is provided by CI. Host equivalence does
not model Adreno command scheduling. There is no reason to promise
substantial FPS gains: on a GPU-bound game, avoided CPU work can be invisible.
Run both old and new binaries to isolate true differences.

Credits: Frane12 tests, Mesa/Freedreno contributors, DiskDVD for A810
descriptor-prefetch diagnostic.
