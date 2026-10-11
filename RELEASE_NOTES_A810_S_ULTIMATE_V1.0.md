# Drnas-Turnip A810 S Ultimate v1.0

**First public release of S Ultimate for Adreno 810**  
Android AArch64 / KGSL · Mesa 26.3.0-devel · Vulkan Turnip

This release packages the **audited RC1 binary unchanged**. Only the installer's displayed name, package version and ZIP filename differ from RC1. No further autotuner changes were made after the successful RC1 Android CI build.

## Features

- **Dynamic V3 category learning:** a lightweight four-slot cache of measured GMEM/SYSMEM winners per render-pass context. It can resume an already learned category when it reappears.
- **Confidence-based decisions:** existing 16-entry AT3 GPU timestamp history remains authoritative; weak, stale, noisy or unmatched measurements cannot force a cached winner.
- **Controlled response:** phase confirmation, winner votes and dwell time reduce rapid GMEM/SYSMEM switching. Fixed A-B-A-B transition counting and a concurrent active-phase recheck in the final audit.
- **Protected rendering:** existing AT4 exploration and AT8/AT7/AT63 selection, depth logic and GMEM safety paths remain available. The regressive AT9 FC2 forced prior is not included.
- **Optional detailed diagnostics:** context decision/cache reasons, GPU timestamp CSV and CPU submission trace are off unless explicitly enabled.
- **DXVK HUD name:** Vulkan reports `Drnas-Turnip A810 S Ultimate v1.0` for A810, which can appear under `DXVK_HUD=devinfo,fps`. Set `TU_FRANE_ULTIMATE_HUD_BRAND=0` to return to the standard GPU name. Original GPU/vendor IDs and pipeline UUID are preserved.

## Compatibility and installation

**Target:** Adreno 810, Android ARM64 with KGSL. This ZIP has been built with the install manifest's `minApi=34`. Other GPU models and other Vulkan/DXVK variants are **not validated**.

Install `Drnas-Turnip-A810-S-Ultimate-v1.0.zip` using your Winlator/Ludashi compatible Turnip driver manager. Choose the driver for your container, fully restart it, and select:

```ini
TU_AUTOTUNE_ALGO=profiled
```

The primary ATUltimate, Dynamic V3, fast learning and cooldown logic are enabled by default; extra env vars are not needed for a normal run.

Optionally use `DXVK_HUD=devinfo,fps` to inspect the GPU name and FPS. Some DXVK builds may abbreviate or omit the device name; the Vulkan `driverInfo` and adapter name have been updated, not the DXVK DLL itself.

## Tuning / rollback

| Variable | Default | Use |
| --- | --- | --- |
| `TU_FRANE_ATU=1` | ON | `0` disables the ATUltimate family toward the AT8 baseline |
| `TU_FRANE_ATU_DYNAMIC=1` | ON | `0` disables dynamic winner routing |
| `TU_FRANE_ATU_V3=1` | ON | `0` compares the previous Dynamic V2 path |
| `TU_FRANE_ATU_FAST=1` | ON | `0` disables the earliest high-confidence 2-pair path |
| `TU_FRANE_ATU_PHASE_HITS=3` | 3 | Increase to 4–5 for less sensitive new-phase detection |
| `TU_FRANE_ATU_DWELL=24` | 24 | Increase to 32–48 for more stable winner switching |
| `TU_FRANE_ULTIMATE_HUD_BRAND=1` | ON | `0` restores native Adreno Vulkan adapter name |

Restart the container after changing runtime variables. Keep Max Frame Latency and other emulator settings consistent during comparisons.

## Optional debug logging

Only activate for a **separate diagnostic session** because CSV writing changes measured FPS:

```ini
TU_AUTOTUNE_ALGO=profiled
TU_FRANE_ATU_CONTEXT_TRACE_PATH=/storage/emulated/0/Download/atu_v1_context.csv
TU_FRANE_A810_RFC1_TRACE_PATH=/storage/emulated/0/Download/atu_v1_gpu.csv
TU_FRANE_A810_CP1_TRACE_PATH=/storage/emulated/0/Download/atu_v1_cpu.csv
```

Confirm your container can write into that Android folder. The context logger reports category identity, cached winner, candidate, votes, cooldown and reasons such as `USED`, `PHASE_WAIT`, `NO_PAIRED`, `NOISY_HISTORY`, `STALE_HISTORY`, `WAIT_DWELL` and `AT4_PRIORITY`. Independent GPU trace timestamps should not be mistaken for frame-perfect joins to context decisions.

## Benchmark evidence and limitations

The strongest **pre-RC Dynamic V3** user Crysis TimeDemo evidence (four passes, 2000 frames each) reported **37.16 average FPS across the warm passes**, and **53.59 seconds / 37.32 FPS** in its quickest individual pass. This is a *reference result for the preceding V3*, **not a benchmark measured on this final audited binary**.

The RC1 source audit, UBSan tests, Android AArch64 build and packaging passed in [GitHub Actions run 38127891483](https://github.com/Frane12/Testturnip/actions/runs/38127891483). No complete multi-game validation or on-device RC1 GPU/context trace is available at the moment of public release. Actual performance and visual behavior can vary with game engine, FEX, DXVK, thermals and device memory pressure.

**Binary provenance:** the `libvulkan_freedreno.so` shipped here has SHA-256  
`55d05eb150d40121770c74fe9c90c3f79b92ea4de28611f2cfce53602e019f80`.  
The RC1 baseline and complete patch set are in the attached source ZIP; a `SHA256SUMS.txt` contains release artifact hashes.

## Download assets

- **`Drnas-Turnip-A810-S-Ultimate-v1.0.zip`** — installable Turnip driver
- **`Drnas-Turnip-A810-S-Ultimate-v1.0-Source.zip`** — audited complete source patch and tests
- **`SHA256SUMS.txt`** — SHA-256 checksums

The code is open for review and testing. Please report the exact device, emulator version, DXVK/FEX combinations and benchmark details when comparing performance.
