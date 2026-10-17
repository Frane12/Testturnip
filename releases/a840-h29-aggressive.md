# Drnas-Turnip NeuroFlow — A840 H2.9 Aggressive

**PRE-RELEASE · TESTING ONLY · EXPERIMENTAL**  
For **Adreno 840 (A840)** · Android ARM64 / KGSL · Mesa 26.3.0-devel · Vulkan Turnip

H2.9 is the tested **aggressive NeuroFlow** development build, published separately from the newer H3.0 decision-cache experiment. Its original H2.9 compiled Vulkan driver is preserved **byte-for-byte**; only the ZIP name and installer's `meta.json` are adjusted for this public test release.

> ⚠️ This is experimental, **not a stable update**. It may have compatibility problems, crashes, visual artifacts or performance regressions on other games/devices. Keep your working driver (for example the previous public A840 H2.8) for rollback. **Do not install on A810 or A830.**

## What's in H2.9

- **A840-specific aggressive NeuroFlow policy**, enabled by default with `TU_FRANE_A840_AGGRESSIVE=1`. Designed to pursue responsive GMEM/SYSMEM decisions under guarded GPU-timed A/B/A comparison.
- **Native Mesa fallback** when the H2.9 decision is invalid, rather than forcing SYSMEM.
- Retains H2.8's **adaptive memory / TEX handling**, confidence checks and guards for stale or noisy measurements.
- Uses the **A840 hardware-specific path**, including the tested GPU chip ID `0xffff44050A31`. Other Adreno chips are not validated.
- Built for **Android ARM64**, with compatible KGSL/Turnip driver managers and **Android API level 34+**.

This is CPU-side learning and GPU timing feedback; it **does not use the Qualcomm Hexagon NPU**.

## Real-device observation (one user test)

On **Poco F8 Ultra / Adreno 840**, **Far Cry 4** at **1280×720**, nearly all settings **Very High** except **Medium shadows**, with **4 CPU cores** and an **FPS cap of 40**, was reported smooth at the 40 FPS lock, with no visible artifacts during that test. This is an individual observation, **not a controlled multi-run benchmark**, and does not prove improvements across other games or longer sessions.

## Installation

1. Download `Drnas-Turnip-NeuroFlow-A840-H2.9-TESTING-ONLY.zip` from the assets below.
2. Install the ZIP with an **AdrenoTools / compatible Winlator Turnip driver manager** in a **separate test container**.
3. Fully restart the emulator / game. Keep DXVK, FEX, resolution, FPS cap, **Max Frame Latency**, CPU affinity and cooling the same when comparing against H2.8 or H3.0.
4. Compare cold and warm runs; note FPS, **frametime / 1% lows**, stutter, temperature, GPU errors and visual correctness. H2.9 may behave differently from H3.0 and H2.8.

For profiled autotuning, use:
```ini
TU_AUTOTUNE_ALGO=profiled
```

## Optional controls

| Variable | Default | Description |
| --- | --- | --- |
| `TU_FRANE_A840_AGGRESSIVE=1` | ON | `0` disables H2.9 aggressive selection while retaining the underlying adaptive path. |
| `TU_FRANE_A840_ADAPTIVE=1` | ON | `0` disables the A840 adaptive controller for an A/B comparison. |
| `TU_FRANE_A840_TEX_DYNAMIC=1` | ON | `0` disables A840 dynamic TEX handling. |
| `TU_FRANE_A840_TRACE=1` | OFF | `1` enables diagnostic traces (with overhead). |

No additional **profile ID** is required for basic H2.9 operation. Use separate game profiles only if you deliberately manage their caches. Restore a known-good driver if you encounter artifacts or instability.

## Provenance / integrity

- Derived from the successful private H2.9 Android ARM64 build of **17 October 2026**.
- Original private driver ZIP SHA-256: `db7de5fb855f35b341939006ebf64d986b0616f50b4c3bc650a9de387bb1d961`.
- The public package changes **metadata only**, preserving the original `libvulkan_freedreno.so` bytes.
- Download `SHA256SUMS.txt` for checksums of the public ZIP and embedded Vulkan binary.

**Author:** Frane12 · **Status:** Experimental / TESTING ONLY · Bug reports and reproducible A/B results welcome.
