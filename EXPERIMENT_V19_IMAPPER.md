# V19 A810 IMapper5 experiment

Base: Frane A810 V18 `2fdc673b319783646874ef91eeeed12f41259b5d`,
Mesa 26.2.3 `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`.

The new backend reads Android gralloc metadata through the stable-C IMapper5
SP-HAL interface. If unavailable at creation, normal Mesa backend selection
continues. `TU_FRANE_AIMAPPER=0` disables it; restart the container after changes.
If a selected mapper cannot describe a buffer, the import fails rather than
guessing its layout. Use the switch if an application encounters this case.

V18 GMEM, memory and sampled-depth policies are preserved. No clock forcing,
new swapchain compression request or global UBWC disable is introduced.

## Provenance

`patches/wn_aimapper/u_gralloc_aimapper.c` derives from the MIT-licensed file
in WinNative-Emu/Drivers, commit `8407c8012d7b3096621becec73d836f4fbe7b3ce`,
`patches/aimapper/u_gralloc_aimapper.c` (v1.17).
Credit: WinNative contributors and Mesa contributors. Original SPDX retained.

Frane port changes: strict integration anchors; rollback switch; bounded metadata
allocation; checked integer conversions; RGB-only two-plane UBWC normalization;
reject multilayer buffers because the 26.2.3 interface lacks the newer array-layout
fields. The original WN source reports validation on A840/Android 16, not A810.

## Device comparison

Use the same game, scene, resolution, DXVK and FPS limit as V18. Test V19 with
no new variables, then `TU_FRANE_AIMAPPER=0`. Confirm the renderer and inspect
the log for `Using IMapper v5 stable-C API via SP-HAL`. Compare texture correctness,
frame time and RAM over at least 15 minutes. No speed or stability claim follows
from compilation alone.
