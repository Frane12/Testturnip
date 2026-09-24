# Frane Turnip V18 — Adreno 830 / internal depth UBWC diagnostic

**Experimental build · Mesa 26.2.3 · Android ARM64 / KGSL**

### Changes
- Carries forward the Frane A830 V16 memory-pressure/autotune and GMEM-lifetime patch stack.
- Adds a reversible **A830-only depth/stencil UBWC A/B diagnostic** for internally allocated images without an explicit DRM modifier.
- Preserves external/AHB layouts, color UBWC, existing GMEM/CCU geometry and V16 memory policies.
- Unlike the A810 V18 sampled-only test, this A830 diagnostic targets applicable internal depth/stencil images more broadly and is **ON by default**.

### Diagnostic switch
| Option | Default | Effect |
| --- | --- | --- |
| `TU_A830_SAFE_DEPTH_UBWC=0` | Diagnostic ON when unset | Turn OFF the V18 A830 depth diagnostic and restore the prior V16 depth-image layout behavior (relaunch game). |

### Package / provenance
- Source: [`mesa-26.2.3-a830-v18-depth-diagnostic`](https://github.com/Frane12/Testturnip/tree/mesa-26.2.3-a830-v18-depth-diagnostic)
- Frane patch commit: `8a1467afa749d0ca9f2fda67eb87bf108876ed97`
- Mesa base commit: `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`
- [Successful GitHub Actions build](https://github.com/Frane12/Testturnip/actions/runs/35745282904)
- Driver ZIP contains `libvulkan_freedreno.so` and `meta.json`; the applied Mesa patch and checksums are attached.

### Feedback / limitations
A community member reported a usable GTA IV session with no freeze in a Wayland-compositor test, but the game used a **different A8XX WHITE driver for rendering**. That report **does not demonstrate an FPS gain or isolate this driver as the game's Vulkan renderer**. Depth/lighting artifacts remain under investigation. Please test with the V18 toggle on/off and report image correctness, FPS/frametime and RAM. Do not flash system/vendor partitions.

### Credits
Frane12 — experimental changes, testing and release; DiskDVD and other A8XX developers — relevant community and upstream-fork work; Mesa/Freedreno/Turnip contributors — underlying driver. **Independent experimental release; not an official Mesa/Turnip release.**
