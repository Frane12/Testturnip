# Frane DXVK 1.10.3 — A810 memory experiment v1

Experimental 32- and 64-bit DXVK 1.10.3 build for Winlator/Bannerlator + Turnip V20. Upstream: doitsujin/dxvk v1.10.3.

## Changes

- Opt-in `DXVK_A810_CHUNK_MB=32`: cap DXVK's Vulkan allocation chunk at 32 MiB (also accepts 16, 64). This does not change Adreno GMEM capacity. It may reduce reserved RAM but increase allocation overhead.
- Optional `DXVK_A810_TRIM_PERCENT=70`: when DXVK allocates more resources, try freeing *already empty* chunks after allocated heap memory passes 70% of the reported Vulkan heap size (also accepts 60, 75). This does not free live resources and may have no visible effect on Android RAM.
- With no env vars, patched allocator uses the original 1.10.3 logic.
- No synchronization removed; flicker fix and FPS gains are not guaranteed.

## Testing

Keep Crysis Warhead, V20 GMEM, OpenGL renderer and identical game settings. First run without env vars; then only `DXVK_A810_CHUNK_MB=32`, then separately test trim percent if memory keeps climbing. Observe DXVK_HUD=memory, frametime, FPS, RAM and sunlight flicker for 15–30 minutes.

## Installation

This build contains x32 and x64 DLLs. For 32-bit games use x32 DLLs; for 64-bit games use x64 DLLs. Back up existing DXVK 1.10.3 first, or import into Bannerlator as a new DXVK version. Don't put DLLs in Turnip's Vulkan .so slot.

Built DLLs appear only if GitHub Actions compilation succeeds.