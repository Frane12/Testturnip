# DRNAS A840 / Mesa 27 — isolated render diagnosis (2026-10-31)

## Confirmed device results
- Working control: Whitebelyash Gen8 (Mesa 26.3.0-devel) + original H2.9 GMEM/SYSMEM adaptive policy. A840 image renders correctly with both `TU_FRANE_A840_ADAPTIVE=1` and `TU_FRANE_A840_AGGRESSIVE=1`.
- Broken control: pinned Mesa 27 commit `1c3a936490f9f0951188218e136cd03bca497386`; vertical striped artifacts in the 3D image, HUD present. The Stage1 observer and H2.9 policy disabled do not correct this.
- Mesa 27 does recognize A840 chip ID `0xffff44050A31` with six CCU units and three slices. Identification by name is NOT the established cause.

## New isolated build
Workflow: `.github/workflows/drnas-a840-mesa27-64k-render-diagnostic.yml`

Pinned upstream Mesa27 commit: `1c3a936490f9f0951188218e136cd03bca497386`.

Changes versus the already broken Mesa27-H2.9 build:
1. Only in the 6-CCU/3-slice Adreno 840 device profile in `freedreno_devices.py`, change `cs_shared_mem_size` from `32 * 1024` to `64 * 1024`. That is the value in the working Gen8 fork. All other A840 properties and other GPU chip IDs remain unchanged.
2. Keep the original private H2.9 CPU GMEM/SYSMEM controller and Stage1 observer, with `TU_FRANE_A840_ADAPTIVE` defaulting **off**.
3. Do not alter upstream Mesa27 shader code, IR3 instruction scheduling, UBWC or raw GPU register tables.
4. Build Android ARM64 KGSL with the same Meson setup as the prior tested driver. Save ZIP in **private draft release only**, never a public artifact.

This is a one-variable hardware-profile experiment, not a confirmed graphics fix. `cs_shared_mem_size` is compute shared memory capacity, *not* GMEM tile memory.

## Phone A/B test matrix
Use the same game save, Winlator, FEX, DXVK, resolution and FPS cap as the broken Mesa27 and working Gen8 tests. Always restart the game after changing environment variables, and use a fresh or separate shader cache when switching driver builds.

| Order | Variables | Interpretation if rendering becomes correct |
|---|---|---|
| A | `TU_FRANE_A840_ADAPTIVE=0` | The isolated A840 64KiB profile is sufficient to remove corruption; validate against exact previous Mesa27 commit and device conditions |
| B | `TU_FRANE_A840_ADAPTIVE=0`, `TU_DEBUG=sysmem` | A GMEM vs SYSMEM render path / tiling / resolve issue is implicated |
| C | `TU_FRANE_A840_ADAPTIVE=0`, `TU_DEBUG=noubwc` | UBWC compression / image layout / resolve is implicated |
| D | `TU_FRANE_A840_ADAPTIVE=0`, `IR3_SHADER_DEBUG=nodescprefetch` | Shader descriptor prefetch behavior is implicated |
| E | `TU_FRANE_A840_ADAPTIVE=0`, `IR3_SHADER_DEBUG=noaliastex` | IR3 texture aliasing path is implicated |

Do not combine B–E initially. For any variant that fixes the picture, repeat twice and test another scene; check FPS and stability. Record the Winlator driver name, chip ID and `TU_DEBUG=startup` information if available.

If all Mesa27 variants still show stripes, keep the working Gen8 driver for normal use, and prepare a version/bisection experiment between Mesa 26.3 and 27 focused on `tu_shader.cc`, input attachments, IR3 / texture descriptors, UBWC, and render pass resolve synchronization. The prior Gen8 result alone cannot prove that the fault was caused by the 32 KiB value.

## Safety / provenance
Original H2.9 private repo is unchanged. New workflow is on experimental public runner branch; H2.9 source is cloned transiently with an Actions secret and final ZIP is released **draft+private**, not made public. Never put tokens in logs, files, or chat.
