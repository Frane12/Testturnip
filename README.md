# Frane Turnip V23 — A810 Lean WSI (experimental)

Android ARM64/KGSL Vulkan Turnip, pinned **Mesa 26.2.3** source
`31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`.

**Base:** V18 A810 sampled-depth + DiskDVD shader workaround and
V22 Lean Profiled autotune. Those reference branches remain unchanged.

V23 adds an A810-only, **embedded Vulkan WSI present-mode preference**:
try MAILBOX if supported by the active Mesa WSI surface, otherwise retain
the application's original mode. This is *not* an OpenGL driver, a Vulkan
API/loader layer, a new display server or a guarantee of smoother FPS.
Explicit `MESA_VK_WSI_PRESENT_MODE` wins; opt out with
`TU_FRANE_PRESENT_MODE=off`.

Read [V23 experiment and testing controls](EXPERIMENT_V23_A810_LEAN_WSI.md).

## Build / download

GitHub Actions workflow **Frane Turnip Mesa 26.2.3 A810 V23 Lean WSI**
runs on pushes to this branch. If successful, it produces
`Frane-Turnip-Mesa-2623-A810-V23-LEAN-WSI.zip` and publishes the test
ZIP, applied source diff and checksums under pre-release
`v23-a810-lean-wsi`.

Never flash the device's system/vendor driver. Compare V23 and V22
with identical FEX, DXVK, game settings and FPS limits.
