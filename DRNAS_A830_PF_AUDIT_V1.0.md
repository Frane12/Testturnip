# Drnas Turnip A830 PF-AUDIT V1.0

Target: **Snapdragon 8 Elite / Adreno 830**

Base: **Drnas Turnip A830 V59 LRZ-CLEAN**.

This branch is deliberately diagnostic. It does not try to "fix" A830 page
faults before we know which GMEM class triggers them. The point is to let normal
Winlator games and benchmarks do the bisection for us.

## One variable

Use only:

`TU_FRANE_PF=<mode>`

Do not combine it with `TU_DEBUG=gmem` or `TU_DEBUG=sysmem` during the first
matrix.

| Mode | Meaning | What a stable result suggests |
|---|---|---|
| 0 | Normal current A830 V59 + V2 | Control |
| 1 | All legal work forced to SYSMEM | If this alone is stable, GMEM path is implicated |
| 2 | Force GMEM whenever Mesa says GMEM is legal | If 2 is stable but 0 faults, selection/transition behavior becomes highly suspicious |
| 3 | Resolve-bearing passes -> SYSMEM | Stability points at resolve/custom-resolve/MSRTSS class |
| 4 | MSAA passes -> SYSMEM | Stability points at multisample GMEM handling |
| 5 | Depth/stencil passes -> SYSMEM | Stability points at D/S GMEM/CCU/LRZ-adjacent class |
| 6 | Any GMEM attachment store -> SYSMEM | Stability points at GMEM tile-store/write-to-system-memory path |
| 7 | Safe-color subset only | GMEM permitted only for single-sample color-only non-resolve passes |
| 8 | A830 V2 learner/boost off | If stable, inspect our stronger measured mode holds / transition pattern |

Modes 3-7 quarantine only the named class. All other render passes retain normal
selection, so an ordinary game or benchmark becomes the test harness.

Mode 2 **does not bypass Mesa correctness gates**. Impossible layouts, empty
render areas, tessellation restrictions, render-pass disable_gmem, XFB/query
restrictions and other mandatory safety checks still force SYSMEM.

## First practical sequence

Use one game/benchmark that is known to reproduce the problem and keep every
other setting identical.

Start with 0 -> 1 -> 2.

Then use 3 -> 4 -> 5 -> 6. Mode 7 is the conservative "is basic color GMEM
healthy?" cross-check. Mode 8 tests whether the A830 V2 selector layer changes
the fault behavior.

Record only: **boots / faults / visible corruption / benchmark completes**.
FPS is secondary for this diagnostic branch.

Once one class cleanly separates stable vs faulting runs, V1.1 can instrument
or fix only that hardware-facing path instead of globally disabling GMEM.
