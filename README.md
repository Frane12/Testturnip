<div align="center">

# Drnas Turnip

**Experimental Mesa Turnip Vulkan drivers for select Qualcomm Adreno GPUs**

Android ARM64 · KGSL · Winlator / compatible userspace driver managers

[![GPU targets](https://img.shields.io/badge/Adreno-A810%20%7C%20A825%20%7C%20A830%20%7C%20A840-6f42c1)](https://github.com/Frane12/Testturnip/releases)
[![Latest A810 release](https://img.shields.io/badge/A810-S%20Ultimate%20v1.0-2ea44f)](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-a810-s-ultimate-v1.0)
[![Experimental](https://img.shields.io/badge/status-experimental-orange)](https://github.com/Frane12/Testturnip/releases)

[**A810 S Ultimate v1.0**](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-a810-s-ultimate-v1.0) · [**NeuroFlow — TESTING ONLY**](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-neuroflow-a8xx-testing-20261016) · [**DRNAS EMU Blender v1.1**](https://github.com/Frane12/Testturnip/releases/tag/blender-v1.1) · [**Native Blender PreAlpha 0.1**](https://github.com/Frane12/DRNAS-Native-Blender/releases/tag/native-prealpha-v0.1) · [**All public releases**](https://github.com/Frane12/Testturnip/releases)

</div>

---

## Overview

Drnas Turnip is an **independent experimental driver project** based on Mesa's Turnip Vulkan driver. It explores workload-aware rendering decisions for Android devices using Qualcomm Adreno GPUs, with particular attention to **GMEM/SYSMEM selection, depth/stencil correctness, GPU timing feedback, frametime behavior and long-session reliability**.

The aim is reproducible improvement, not an impressive result from one benchmark pass. Different GPU generations are treated as separate targets; optimizations and safety assumptions are **not** assumed to transfer between chips.

> **Status:** These are community experimental builds, not official Mesa or Qualcomm releases. A public release is **not** a certification of universal stability, compatibility or performance gains.

## DRNAS EMU · Blender on Android (experimental preview)

Alongside the Turnip driver research, **DRNAS EMU** is an experimental Android ARM64 compatibility environment for Windows desktop applications, with a focus on creative and productivity tools. Its first public application preview runs **Blender 4.5.14 LTS (Windows ARM64)** on Android through a Wine/X11/Vulkan-based integration layer.

**[Download DRNAS Blender v1.1 — ARM64 Android Preview (APK)](https://github.com/Frane12/Testturnip/releases/tag/blender-v1.1)** · **Public prerelease / testing only**

- **Touch-oriented Blender workflow:** 3D viewport interaction, on-screen mouse buttons and keyboard, smooth zoom control, and a DRNAS-managed fullscreen option.
- **Project files:** select an Android folder at startup; it appears as **`D:\`** in Blender for opening and saving projects.
- **Experimental GPU paths:** automatic selection/fallback for supported Adreno, eligible Mali, and Samsung Xclipse devices. The **Adreno 840** has been exercised on-device; broad GPU compatibility is **not** guaranteed.

This is **not a native or official Blender Android release** and is **not affiliated with the Blender Foundation**. Startup, installation, rendering and secondary windows may still fail on some devices. Save backups of important `.blend` files and check the [v1.1 release notes](https://github.com/Frane12/Testturnip/releases/tag/blender-v1.1) for setup, limitations and troubleshooting.

## Native Blender PreAlpha 0.1 — a separate Android track

[**DRNAS Native Blender repository**](https://github.com/Frane12/DRNAS-Native-Blender) · [**PreAlpha 0.1 release page**](https://github.com/Frane12/DRNAS-Native-Blender/releases/tag/native-prealpha-v0.1) · [**Source, tests and roadmap**](https://github.com/Frane12/DRNAS-Native-Blender#readme)

DRNAS is exploring a **second, independent** approach to Blender on Android:

| | **DRNAS EMU Blender v1.1 (this repository)** | **DRNAS Native Blender PreAlpha 0.1** |
| --- | --- | --- |
| Blender executable | Blender **4.5.14 LTS Windows ARM64** | Android **ARM64 native lite** build |
| Integration | **Wine/X11/Vulkan compatibility environment** | Native Android GHOST/JNI and experimental Vulkan viewport |
| Windows compatibility layer | Yes (ARM64 app; not automatically x86 emulation) | No |
| Current evidence | Public preview; basic viewport editing and zoom exercised on Adreno 840 | Build-time checks; hardware rendering and device support still require validation |
| Trade-off | Broader Windows desktop application workflow, with compatibility overhead | Potentially simpler native stack, with **lite/incomplete features** |

**Pre-alpha is not a stability or speed claim.** Both approaches are experimental; neither is an official Blender Foundation Android release. The native APK has **its own package ID** and does **not** replace DRNAS EMU. Native 0.1 APK availability depends on successful build, signing and packaging checks. Details, source attribution and testing priorities are documented in its own repository.

---

## Published driver options

Only **publicly published** releases are listed here. Follow each release page for its exact compatibility requirements, package and test status.

| GPU | Public release | Status / intended use |
| --- | --- | --- |
| **Adreno 810** | [**S Ultimate v1.0**](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-a810-s-ultimate-v1.0) | Main A810 public package; adaptive render policy. Still experimental. |
| **Adreno 810** | [**S1**](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-s1-a810) | Earlier public endurance/reference candidate. |
| **Adreno 825** | [**S Ultimate v0.1 D1 TEST**](https://github.com/Frane12/Testturnip/releases/tag/a825-s-ultimate-v0.1-d1-test) | Hardware-validation test; startup and rendering not yet confirmed on device. |
| **Adreno 830** | [**S1 Smart Performance**](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-s1-a830-smart) | Experimental guarded GMEM and scene-history policy. |
| **Adreno 830** | [**S2-BW1**](https://github.com/Frane12/Testturnip/releases/tag/a830-s2-bw1-internal) | Experimental bandwidth / tile-memory policy; hardware results needed. |
| **A810 / A830 / A840** | [**NeuroFlow**](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-neuroflow-a8xx-testing-20261016) | **Prerelease · TESTING ONLY.** Three GPU-specific packages. |

**For an A810 public starting point**, use **S Ultimate v1.0** and its release notes. Keep S1 or another known-good driver available for rollback. **NeuroFlow is a separate experimental test track**, not a replacement declared more stable or faster.

### A810 S Ultimate v1.0

The published A810 package combines bounded GPU timing evidence with adaptive GMEM/SYSMEM decisions, confidence checks, phase-change confirmation and cooldowns. Guarded rendering paths remain available when evidence is insufficient.

- **Target:** Adreno 810, Android ARM64 / KGSL; the package specifies **minimum Android API 34**.
- **Installation:** Import `Drnas-Turnip-A810-S-Ultimate-v1.0.zip` in a compatible Turnip driver manager.
- **Recommended autotuner:** `TU_AUTOTUNE_ALGO=profiled`.
- **Default behavior:** Main adaptive controls are enabled; additional `TU_FRANE_*` overrides are not needed for an initial test.
- **Validation boundary:** Source auditing, automated tests and Android build checks are documented in the release notes. Complete multi-game validation of the final public binary is **not** claimed.

See the [A810 release notes, available source archive and checksums](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-a810-s-ultimate-v1.0).

### NeuroFlow — testing only

NeuroFlow investigates lightweight, feedback-driven adaptation with **different compiled drivers for each target GPU**.

| GPU | Public package | Research focus |
| --- | --- | --- |
| A810 | `Drnas-Turnip-NeuroFlow-A810-H2.7-TESTING-ONLY.zip` | Dynamic shader TEX windows with GPU timestamp feedback |
| A830 | `Drnas-Turnip-NeuroFlow-A830-H2.4-TESTING-ONLY.zip` | Confidence-controlled learning and warm-start cache |
| A840 | `Drnas-Turnip-NeuroFlow-A840-H2.8-TESTING-ONLY.zip` | Adaptive memory and GMEM/SYSMEM decisions |

**Do not cross-install GPU packages.** The A840 test is restricted to the hardware scope specified in its release notes. NeuroFlow currently uses CPU-side policy and existing GPU timing feedback; **it does not run inference on the Qualcomm Hexagon NPU**.

These test builds may exhibit visual corruption, depth/shadow errors, startup failures, memory regressions or device loss. **No universal FPS or endurance claim is made.** See [NeuroFlow compatibility, controls and test instructions](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-neuroflow-a8xx-testing-20261016).

---

## Installation

1. **Confirm the exact GPU** and read the target release notes, including Android/API, KGSL and driver-manager requirements.
2. Download the **installable driver ZIP for that GPU** from its published release. Do not substitute a source ZIP or flash it as system firmware.
3. Import the ZIP using a compatible Winlator/Ludashi/AdrenoTools-style driver manager and select it for the test container.
4. **Fully restart** the container/game after switching drivers or environment variables.
5. Begin with release defaults. Where applicable, use `TU_AUTOTUNE_ALGO=profiled`; avoid stacking untested overrides.
6. Preserve a **known-working driver** and a separate test container for easy recovery.

Where provided, verify the downloaded files using the release's `SHA256SUMS.txt`. Driver selection, supported package format and Vulkan integration depend on the application/device; installability does not guarantee correct rendering.

## Testing and evidence

**Compile success, host-side tests, synthetic policies and on-device gameplay are different levels of evidence.** Neither successful packaging nor one high-FPS run proves broad driver correctness.

For a meaningful A/B comparison, keep the following constant:

- Exact device, Android build, emulator/Winlator build and GPU driver selection.
- Game version, scene, resolution, graphics settings and FPS cap.
- Wine/Proton, DXVK/VKD3D and FEX/Box64 versions.
- CPU affinity, present mode, frame-latency settings and cooling conditions.
- Cache state and run order; record at least one cold launch and multiple warm runs.

Report **average FPS, 1% lows or representative frametimes, run duration, RAM/memory growth, thermals, artifacts and crashes**. Results from one game/scene should never be presented as universal device improvements.

### Public reference observations

The following are **development observations**, not guarantees for newer packages:

| Published A810 reference | Observation | Evidence |
| --- | --- | --- |
| [V38 GMEM-SEARCH](https://github.com/Frane12/Testturnip/releases/tag/a810-v38-gmem-search) | Used repeatedly to compare aggressive GMEM behavior in CryEngine/Dirt 3 development testing. | Repeated reference |
| [V57 PROFILED-TAIL-GUARD](https://github.com/Frane12/Testturnip/releases/tag/a810-v57-profiled-tail-guard) | Reference for controlling expensive/ambiguous GMEM tail cases using measured policy decisions. | Repeated reference |
| [S1 A810](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-s1-a810) | Far Cry 3 was observed around **38–40 FPS** in the recorded test setup; this is not a cross-device average. | Observed |

Later public releases include additional implementation and validation details on their own pages. When claiming a performance difference, specify **which binary was actually measured**.

### Report a result or regression

Use [GitHub Issues](https://github.com/Frane12/Testturnip/issues) and include:

```text
GPU / exact device / Android:
Driver release and ZIP:
Winlator or driver manager:
Wine/Proton + FEX/Box64 + DXVK/VKD3D:
Game, scene, resolution and graphics settings:
Cold run / warm runs:
Average FPS and frametime or 1% low:
RAM, thermals and duration:
Artifacts, freezes, page faults or crashes:
Comparison driver and reproducible steps:
```

Please attach logs or screenshots where useful. A regression report is as valuable as a performance improvement.

## Technical focus

- Safe, workload-aware **GMEM/SYSMEM** selection and tile-memory behavior.
- **Depth/stencil, LRZ, resolves, barriers and render-pass correctness**.
- **GPU timestamp feedback** with freshness, confidence and noise handling.
- Bounded scene/context history, adaptive probing and controlled fallback.
- Command submission, shader-path experiments and frametime consistency.
- Memory behavior, repeatable benchmarks and long-session stability.

The project modifies userspace driver behavior; it **does not require modifying the Android vendor partition**.

## Source, attribution and scope

Drnas Turnip builds on the open-source [Mesa / Turnip project](https://docs.mesa3d.org/drivers/freedreno.html). Source archives and checksums are provided **where attached to a specific public release**; consult that release for build provenance and included materials.

This is an independent experimental effort, not an official upstream Mesa, Qualcomm or emulator-vendor release. Contributions and reproducible feedback are welcome through [GitHub Issues](https://github.com/Frane12/Testturnip/issues).

---

<div align="center">

**Correctness first · Measured performance · Reproducible results**

[**Browse published releases**](https://github.com/Frane12/Testturnip/releases)

</div>
