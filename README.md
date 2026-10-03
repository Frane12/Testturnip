<div align="center">

# Drnas Turnip

### Experimental Turnip Vulkan drivers for Adreno 810

**Android ARM64 · KGSL · Winlator / AdrenoTools**

[![Release](https://img.shields.io/badge/release-Drnas--Turnip_S1_A810-2ea44f?style=for-the-badge)](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-s1-a810)
[![GPU](https://img.shields.io/badge/GPU-Adreno_810-6f42c1?style=for-the-badge)](https://github.com/Frane12/Testturnip)
[![Status](https://img.shields.io/badge/status-endurance_validation-blue?style=for-the-badge)](https://github.com/Frane12/Testturnip/releases)

**Measured render-policy work focused on real game performance, frametime behavior and long-session stability.**

[Download S1](https://github.com/Frane12/Testturnip/releases/download/drnas-turnip-s1-a810/Drnas-Turnip-S1-A810.zip) ·
[Release notes](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-s1-a810) ·
[All releases](https://github.com/Frane12/Testturnip/releases)

</div>

---

## Current release — Drnas-Turnip S1 A810

**S1 is the current A810 release and the first stability / endurance milestone after the main performance-tuning phase.**

Rather than continuing to change policy after every benchmark, S1 freezes the current render stack so it can be tested across longer real-game sessions, scene changes and different workloads.

| | |
|---|---|
| **Target GPU** | Qualcomm Adreno 810 |
| **Platform** | Android ARM64 / KGSL |
| **Base** | Mesa 26.3.0-devel snapshot |
| **Phase** | Stability / endurance validation |
| **Recommended autotuner** | Mesa PROFILED |
| **Manual overrides** | Not required for normal S1 use |
| **Package** | AdrenoTools / Winlator-compatible ZIP |

### What is inside S1

- **PROFILED Tail Guard** — protects expensive or ambiguous GMEM tail cases and can return uncertain decisions to Mesa's PROFILED autotuner.
- **Tail Learner** — uses bounded GMEM/SYSMEM timing evidence instead of reacting to isolated frames.
- **Frequency-Aware Scan** — spends learning work primarily on render passes that recur often enough to justify it.
- **Signature-Gated Scan** — avoids unnecessary forced scanning on cold or rare passes.
- **GMEM/SYSMEM policy work** — tuned around measured workload behavior rather than blindly forcing one path.
- **Depth and GMEM safety logic** — keeps performance experiments behind correctness-oriented guards.
- **Scheduler and command-buffer tuning** — retained from the proven A810 development stack.
- **Mesa PROFILED cooperation** — the custom policy is designed to defer when confidence is insufficient.

The goal is not to force every frame into the same path. The goal is to make better decisions while keeping the cost of making those decisions small.

---

## Recommended reference setup

This is the current reference environment used for controlled comparison:

| Component | Recommended |
|---|---|
| Vulkan renderer | **System / FIFO** |
| Vulkan present mode | **MAILBOX** |
| Autotuner | **PROFILED** |
| FEX | **2609** |
| DXVK | **1.9.4** |
| `TU_FRANE_*` | **Default / no manual overrides** |

Different games can prefer different combinations, but keeping a fixed reference stack makes A/B testing far more useful.

---

## Quick start

1. Download **Drnas-Turnip-S1-A810.zip** from the current release.
2. Import the ZIP through a compatible AdrenoTools / Winlator userspace driver loader.
3. Start with the driver defaults and **do not add manual `TU_FRANE_*` variables**.
4. Use **PROFILED** autotuning for the intended S1 behavior.
5. Keep a known-good driver available for rollback while testing experimental builds.

### SHA-256

The release also includes **SHA256SUMS.txt** so the downloaded driver package can be verified before testing.

---

## Testing philosophy

This project is built around repeatable behavior, not a single spectacular benchmark frame.

Useful comparisons should keep the same:

- game and scene;
- resolution and graphics settings;
- DXVK / Wine / Proton / FEX stack;
- benchmark pass count;
- cache state where possible;
- thermal conditions as consistently as practical.

Warm runs and repeated passes are more useful than over-interpreting a single minimum-FPS event. Long-session testing matters because a fast driver that develops RAM growth, visual corruption, hangs or frametime drift is not a successful driver.

### S1 endurance focus

Current S1 testing is specifically watching for:

- RAM growth during long sessions;
- frametime drift after warm-up;
- hangs, freezes and device-lost events;
- intermittent visual corruption;
- behavior across scene / level changes;
- whether learned GMEM/SYSMEM decisions remain sensible as workloads change.

---

## Experimental game adaptation

`TU_FRANE_PROFILE_ID` is an **experimental workload/profile adaptation hook**.

It exists for controlled game-specific experiments, but it is **not part of the recommended S1 endurance default**. Normal S1 testing should be performed without a manual profile override unless a specific experiment calls for one.

---

## Development milestones

S1 is built on the useful results gathered through the A810 experimental series.

| Milestone | Main idea |
|---|---|
| **V39 — GMEM-PRESSURE** | Future-aware GMEM search / pressure bound |
| **V47 — CB-PROFILER** | Concurrent-binning profiling and control |
| **V52 — CLEAN-INTERFACE** | Standardized `TU_FRANE_*` experimental controls |
| **V54 — UPPER-PROBE** | Crysis depth / GMEM reference work |
| **V56 — GMEM-HARD-PUSH** | Aggressive measured GMEM boundary testing |
| **V57 — PROFILED-TAIL-GUARD** | Measured escape path for expensive tail passes |
| **S1 — A810** | Frozen performance stack moved into endurance validation |

Intermediate builds are development probes. Public releases are kept primarily for meaningful milestones, references and reproducible comparisons.

---

## A830 work

The repository also contains **experimental Adreno 830 work**, but the current S1 release is specifically targeted at **Adreno 810**.

A830 is treated as a separate hardware target: A810-specific assumptions, GMEM limits or workarounds are not blindly copied across GPU generations.

---

## Project scope

Drnas Turnip is an experimental userspace Vulkan-driver project focused on exploring Mesa Turnip behavior on Android.

Current areas of work include:

- GMEM vs SYSMEM selection;
- GMEM allocation and search;
- depth/stencil handling;
- LRZ-safe behavior;
- concurrent binning;
- render-pass recurrence and policy learning;
- shader / pipeline efficiency;
- command-buffer and scheduling behavior;
- Winlator-oriented game testing.

The project **does not modify the Android vendor partition**.

---

## Important

These are experimental drivers. Performance and compatibility vary by device, game, Android build and userspace stack.

A benchmark gain in one engine is not presented as a universal performance claim. Correctness, repeatability and endurance are treated as part of performance, not as separate afterthoughts.

---

<div align="center">

### Drnas Turnip S1 A810

**Performance tuned. Policy frozen. Endurance testing in progress.**

[Download](https://github.com/Frane12/Testturnip/releases/download/drnas-turnip-s1-a810/Drnas-Turnip-S1-A810.zip) ·
[Release notes](https://github.com/Frane12/Testturnip/releases/tag/drnas-turnip-s1-a810)

</div>
