# Frane Turnip V18 — Adreno 810 / sampled-depth diagnostic

**Experimental build · Mesa 26.2.3 · Android ARM64 / KGSL**

### Changes since V17 A810
- Retains the V17 A810 patch stack and DiskDVD-derived descriptor-prefetch workaround.
- Adds **`TU_A810_SAMPLED_DEPTH_DIAG=1`**, an opt-in test that disables UBWC only for **internally allocated sampled/input-attachment depth/stencil images on supported A810 IDs**.
- Leaves color UBWC, explicitly specified external DRM modifier layouts, other GPU families and GMEM selection unaffected by this new toggle.
- Keeps V17's broader A810 depth and burst tests independently configurable and OFF by default.

### Diagnostic switches
| Option | Default | Effect |
| --- | --- | --- |
| `TU_A810_SAMPLED_DEPTH_DIAG=1` | OFF | Enable the new narrow sampled-depth UBWC A/B test. |
| `IR3_A810_DISKDVD_PREFETCH=0` | Workaround ON when unset | Disable the descriptor-prefetch workaround for A/B testing. |
| `TU_A810_SAFE_DEPTH_UBWC=1` | OFF | Enable the *separate, broader* V17 depth test. |
| `TU_A810_GMEM_BURST=1` | OFF | Enable the V17 GMEM-burst experiment. |

### Package / provenance
- Source: [`mesa-26.2.3-a810-v18-depth-sampled`](https://github.com/Frane12/Testturnip/tree/mesa-26.2.3-a810-v18-depth-sampled)
- Frane patch commit: `2fdc673b319783646874ef91eeeed12f41259b5d`
- Mesa base commit: `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`
- [Successful GitHub Actions build](https://github.com/Frane12/Testturnip/actions/runs/35864298649)
- [Related upstream-fork diagnostic proposal: DiskDVD/A8XX-Y #79](https://github.com/DiskDVD/A8XX-Y/pull/79). That PR is **not** evidence that this release is merged into Mesa or DiskDVD's main branch; this binary is built from **Frane12/Testturnip**, not the later edited PR commit.
- Driver ZIP contains `libvulkan_freedreno.so` and `meta.json`; the applied source diff and checksums are attached.

### Test guidance / limitations
Compare the same scene with the new variable unset and set to `1`, relaunching the game between runs. Capture image correctness (particularly camera-relative light/shadow rectangles), FPS/frametime and RAM. The new switch is a **diagnostic, not a confirmed fix**; a successful CI build alone does not establish device stability. Do not flash system/vendor partitions.

### Credits
Frane12 — experiment, port, testing and release; DiskDVD — underlying IR3 workaround and review activity; Mesa/Freedreno/Turnip contributors — core driver. **Independent experimental release.**
