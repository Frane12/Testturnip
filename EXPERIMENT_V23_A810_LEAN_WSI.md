# Frane Turnip V23 A810 — Lean Profiled + embedded WSI experiment

**Baseline:** V22 Lean Profiled built from V18 on pinned Mesa 26.2.3,
commit `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`.
V18 sampled-depth / DiskDVD workaround and all V22 autotune changes remain.
V22 and V18 branches are untouched.

## Experimental presentation preference

V23 configures the **existing Mesa Vulkan WSI inside Turnip**, not a new
OpenGL implementation or a Vulkan loader layer. On the two known A810
chip identifiers it defaults to preferring MAILBOX on each swapchain;
Mesa checks the surface-reported present modes and **falls back to the
application's requested mode if MAILBOX is unsupported**. The preferred
mode is selected at process/physical-device initialization. This does NOT
dynamically measure latency or guarantee that the Android/X11 backend
honors the Mesa common WSI preference.

The GPU render mode, GMEM autotuner, frame limits, swapchain image
lifetime, synchronization, barriers, and other A8xx chips are unchanged.
No additional rendering thread or presentation queue is created.

## Controls (relaunch Winlator container/game after each change)

| Environment | Meaning |
| --- | --- |
| *(unset)* | Prefer MAILBOX on supported A810 WSI swapchains |
| `TU_FRANE_PRESENT_MODE=off` | V22 original application-defined presentation |
| `TU_FRANE_PRESENT_MODE=mailbox` | Explicit MAILBOX preference |
| `TU_FRANE_PRESENT_MODE=fifo` | Prefer FIFO where supported |
| `TU_FRANE_PRESENT_MODE=relaxed` | Prefer FIFO_RELAXED where supported |
| `TU_FRANE_PRESENT_MODE=immediate` | Prefer IMMEDIATE where supported, tearing possible |
| `TU_FRANE_PRESENT_LOG=1` | Log selected preference at WSI init, not actual compositor display timing |
| `MESA_VK_WSI_PRESENT_MODE=...` | Explicit Mesa override wins over TU_FRANE_PRESENT_MODE |
| `TU_A810_LEAN_PROFILED=0` | Retain original V22 profiling A/B rollback |

Use the same FEX 2609, Sarek async 1.10.8, resolution, cooling, limit and
FC3 location as V18/V22. Compare no variable vs
`TU_FRANE_PRESENT_MODE=off` and `TU_FRANE_PRESENT_MODE=fifo` before
changing GPU autotune. A value of "auto" means try MAILBOX and use Mesa's
fallback; it is NOT refresh-rate-based mode selection.

## Build and limitations

GitHub Actions checks the unchanged V18 probability update and V22 policy
unit test, additionally tests presentation setting parsing, applies V23 on
pinned Mesa and compiles Android ARM64 KGSL, publishing the AdrenoTools ZIP,
applied source diff and SHA256 checksums when successful. Host tests do not
establish that Android's native surface path honors the swapchain override.
Do NOT install this as a system vendor driver. If the result is worse or shows
tearing, revert via `TU_FRANE_PRESENT_MODE=off` or restore V22.

This experiment cannot cure Vulkan texture artifacts, GPU page faults, or
DXVK bugs. It can at most change presentation queuing, if the active WSI
path consumes the common override.

Credit: Frane12, Mesa/Freedreno, DiskDVD.
