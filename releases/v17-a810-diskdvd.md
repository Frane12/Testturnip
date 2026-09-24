# Frane Turnip V17 — Adreno 810 / DiskDVD diagnostic

**Experimental build · Mesa 26.2.3 · Android ARM64 / KGSL**

### Changes
- Ported the Frane A810 bounded-GMEM and memory-pressure experiments onto a pinned Mesa 26.2.3 base.
- Adapted DiskDVD's A810 IR3 descriptor-prefetch workaround as an A810-only, reversible diagnostic.
- Kept earlier broad depth/UBWC and GMEM-burst tests available, **disabled by default**, so the shader experiment can be compared separately.
- Includes previously developed memory/autotune and KGSL correctness changes. **No guaranteed FPS, RAM, or artifact improvement.**

### Diagnostic switches (environment variables)
| Option | Default | Effect |
| --- | --- | --- |
| `IR3_A810_DISKDVD_PREFETCH=0` | Workaround ON when unset | Disable the A810 descriptor-prefetch workaround for A/B testing. |
| `TU_A810_SAFE_DEPTH_UBWC=1` | OFF | Try the broader A810 depth/UBWC diagnostic. |
| `TU_A810_GMEM_BURST=1` | OFF | Enable the experimental A810 GMEM-burst policy. |

### Package / provenance
- Build source branch: [`mesa-26.2.3-a810-v17-diskdvd`](https://github.com/Frane12/Testturnip/tree/mesa-26.2.3-a810-v17-diskdvd)
- Frane patch commit: `f391126627bd6c56fdc41771de77928d2395ddfa`
- Base Mesa source commit: `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`
- [Successful GitHub Actions build](https://github.com/Frane12/Testturnip/actions/runs/35738605867)
- Driver ZIP contains `libvulkan_freedreno.so` and `meta.json`. The full applied Mesa diff and checksums are attached separately.
- The original V17 build artifact had an inherited **LIGHT-BURST** name in `meta.json`; the release ZIP corrects that display-name/description mismatch **without modifying the compiled .so**.

### Known limits
This is a test build, **not a verified fix for D3D11 flickering / lighting rectangles**. Compare against a known-good driver; report device, game, DXVK version, switches, FPS, RAM, and image correctness. Avoid flashing system/vendor partitions.

### Credits
Frane12 — experimental port, hardware testing and release; DiskDVD — underlying A810 descriptor-prefetch workaround; Mesa/Freedreno and previous Turnip contributors — driver foundation. This is an **independent experimental build, not an official Mesa or DiskDVD release**.
