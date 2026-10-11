# Turnip-Drnas U1 RC1 — Universal A810 · INTERNAL DRAFT

**Mesa base:** 26.3.0-devel, commit `eda9aceb39d5ff169b096444abe366bdf2269e24`.
**Devices:** exact Adreno 810 chip IDs (`0x44010000`, `0xffff44010000`), Android AArch64 KGSL, Android 14/API 34+.

This **Release Candidate 1** uses our best measured Crysis baseline (AT6.3 EarlyWinner without AT5), adds the existing AT7 bounded GPU-time utility promotion and CP1 empty-command-list fastpath, each independently revertible. It does not insert game/engine names in the driver's policy, bypass the GMEM/depth/stencil safety checks, or add new GPU timestamp queries. **Multi-engine validation is still pending.**

## Default behavior

No environment variables are needed to enable the A810 optimizations. On the recognized A810 and eligible rendering contexts:

| Feature | Default | Turn off |
| --- | --- | --- |
| Mesa profiled autotune (A810) | ON (if ALGO unspecified) | `TU_AUTOTUNE_ALGO=default` to use Mesa's normal selection |
| AT1 contextual decisions | ON | `TU_FRANE_AT1=0` |
| AT3 history and learning | ON | `TU_FRANE_AT3=0` |
| AT4 guarded renderer | ON | `TU_FRANE_AT4=0` |
| AT6 class priors | ON | `TU_FRANE_AT6=0` |
| AT6.3 EarlyWinner | ON | `TU_FRANE_AT63=0` |
| AT7 conservative utility gate | ON | `TU_FRANE_AT7=0` |
| CP1 skip empty command batches | ON | `TU_FRANE_CP1_ZERO_SKIP=0` |
| GPU decision/timestamp CSV | **OFF** | enable with the path variable below |
| CPU queue submit CSV | **OFF** | enable with the path variable below |

Disabling earlier AT layers implicitly disables dependent layers; disable only
the named feature for controlled A/B. The A810 safety gate remains in place.
Experimental stencil/depth correctness relaxations are intentionally not
forced ON; safety and visuals outrank default aggression. Changing options
requires a **new Winlator/container process**.

## Logging, separately optional

**GPU per-render-pass decisions and hardware time**:

```ini
TU_FRANE_A810_RFC1_TRACE_PATH=/sdcard/Download/turnip_a810_u1_gpu.csv
```

**CPU queue submission** (lock wait / patchpoint / commands / autotuner /
driver submit and post-submit times):

```ini
TU_FRANE_A810_CP1_TRACE_PATH=/sdcard/Download/turnip_a810_u1_cpu.csv
```

Either variable can be enabled independently, both together, or neither.
The paths must be **absolute, writable paths visible inside the emulator
process**; Android permissions may require app-private directories.
Both CSVs sample and may cause FPS overhead. With both unset the
diagnostic file I/O and timestamp collection are disabled.
The GPU logger uses existing per-pass GPU timestamps, in ns. The CPU
logger uses `CLOCK_MONOTONIC` for CPU phases only, never GPU frame time.
For FPS benchmarks, **leave both log variables unset.**

## Regression-first promotion criteria

U1 RC1 is a testing draft, *not* a proven universal stable driver.
Benchmark three warm runs per engine with the same DXVK/FEX/resolution,
Max Frame Latency settings, starting temperatures and comparable scenes.
Minimum matrix: Crysis/Warhead (CryEngine 2), Far Cry 2 (Dunia),
Far Cry 3 (Dunia 2), DiRT 3 (EGO), GTA IV (RAGE), Tomb Raider 2013
(Crystal Engine), and optionally Source (Left 4 Dead 2) plus Eden/Switch
compatibility. Track average FPS, 1% low/frametime, temperature/RAM,
artifacts and crashes.

Compare U1 with **AT7=0, CP1=0** on the *same binary* first.
The measured prior AT6.3 reference in Crysis was about 36.15 FPS /
55.32 s on three warm runs. This is not a universal expected result.

If gains are below ~1% or are within repeatability noise, leave optional
feature OFF for the eventual stable profile. Revert immediately if a game
has new visual artifacts, hangs, memory regressions or reliable >3% FPS
loss. Do not call RC1 stable until several engines pass the regression
matrix.

## Distribution

This build is a **GitHub draft release only**. Draft releases are not
published in the public release feed. The repository itself currently has
**public** visibility, so GitHub source branches may be visible; a draft
release is not the same as a private repository. No release is published
publicly by this workflow.
