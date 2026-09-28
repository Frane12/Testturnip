# Frane Mesa 26.3.26 A810 GMEM-SAFETY EXP

Based on the green 26.3.25 scheduler-tuned A810 branch.

Hardware A/B showed clean forced SYSMEM and reproducible corruption when
autotune selected GMEM, including stock Turnip. This build keeps GMEM only for
structurally low-risk autotuner passes and falls back to SYSMEM otherwise.

Default safe class: full-frame, single-layer, single-subpass, single-sample,
valid tiling, no FDM/multiview/MSRTSS/conditional load-store/input/resolve/
feedback/raster-order attachment access, at most four attachments, and no
depth/stencil GMEM attachment.

A/B:
- TU_A810_26326_GMEM_SAFETY=0 disables the gate.
- TU_A810_26326_GMEM_ALLOW_DEPTH=1 permits otherwise-simple depth/stencil GMEM.

Explicit driver-required early GMEM paths are not changed. Vulkan sync, GPU
register programming, 26.3.25 scheduler tuning, LRZ-safe stack and SMART-GMEM
remain intact.
