# Blender v1.1 — ARM64 Android Preview

**Unofficial experimental release.** Blender 4.5.14 LTS (Windows ARM64) running on Android through the DRNAS Wine/X11/Vulkan compatibility environment. Not an official Blender Foundation app.

## Highlights

- **Smooth 3D viewport zoom:** floating ZOOM slider with smooth distance interpolation; +/− buttons and long-press ZOOM for the wheel fallback.
- **Safe fullscreen:** Blender's Window → Toggle Window Fullscreen (DRNAS) changes Android's display layout, avoiding a native Wine fullscreen transition that previously froze the GUI.
- **Touch-friendly editing:** compact mouse pointer, LMB/RMB and collapsible Blender keyboard with tested sizing.
- **Android project folder D:\\:** choose the project folder at startup, then use D: in Blender's Open/Save dialog.
- **Quiet performance defaults:** expensive continuous X11 frame/input tracing, stack watchdog and PanVK startup debug disabled; lightweight error logs, manually enabled diagnostic logging and timed performance tests remain.

## GPU auto-selection (experimental)

| GPU | Automatic Vulkan route | Current status |
| --- | --- | --- |
| **Adreno A6xx/A7xx** (recognized models) | Mesa Turnip candidate → system Vulkan fallback | Chip-family selection implemented; per-device results vary |
| **Adreno 810 / 830 / 840** | Matched DRNAS Turnip/NeuroFlow candidate → system fallback | **Adreno 840 used successfully** for editing and zoom; other chips not all verified |
| **Mali G52 / G72 / G76** | Matched experimental PanVK candidate on eligible Android versions → system fallback | Experimental, not confirmed on every device |
| **Other Mali chips** (e.g., G57/G610/G720) | Firmware system Vulkan; no unsupported PanVK injection | Unverified; depends on device firmware |
| **Samsung Xclipse** (e.g., Xclipse 920/940) | Samsung/AMD firmware Vulkan **only**, never Turnip/PanVK | Auto-detection implemented; **Xclipse 940 rendering not yet device-verified** |
| Other Vulkan-capable Android devices | Firmware Vulkan | Compatibility not guaranteed |

*Detecting a GPU or passing a Vulkan preflight does not guarantee Blender renders successfully. Actual support depends on GPU driver, Vulkan features and Wine's presentation path. Samsung proprietary Vulkan drivers are not bundled.*

## Setup

1. Download **Blender-v1.1-ARM64-Android-Preview-VULKAN-STABLE-SIGNED.apk**. Install on ARM64 Android and allow access to an Android folder when prompted.
2. Choose your project directory. Blender's Open/Save dialog exposes it as **D:\\**.
3. Wait for Blender's Windows ARM64 environment to start. Start with the default cube.
4. Use ZOOM, mouse buttons and keyboard toolbar to work. For fullscreen, use the **DRNAS** option, not native Wine fullscreen commands.
5. If a GPU or input issue occurs, open the in-app menu and export a log. Enable detailed diagnostics only for troubleshooting.

## Known limitations

This is not a native Blender Android build. Loading, rendering, ray tracing, large scenes, file dialogs and individual GPUs may behave differently across devices. Save frequently and back up your .blend projects. The safe Android fullscreen is a workaround; native Wine fullscreen is not fully implemented.

## Attribution and source

Blender, Wine/Proton, Mesa Turnip/PanVK, DXVK, FEX and X11 libraries are third-party projects with separate open-source licenses. Their copyrights and licenses remain with their contributors. This APK is unofficial, and no upstream project endorses it.

For Blender upstream source and license, see [Blender's source repository](https://projects.blender.org/blender/blender) and [Blender's license information](https://www.blender.org/about/license/). Wine/Proton and Mesa upstream development sources are available at [WineHQ](https://gitlab.winehq.org/wine/wine), [Valve Proton](https://github.com/ValveSoftware/Proton), and [Mesa](https://gitlab.freedesktop.org/mesa/mesa). Those links identify upstream projects; they do not by themselves document all bundled exact revisions or modifications. License notices for bundled components must be honored; corresponding-source requests and redistribution compliance remain the publisher's responsibility.

**Warning:** GitHub's automatically generated "Source code" archives on this Testturnip release contain the Testturnip repository tree, **not** the complete source for all bundled APK components.

Feedback: include your device model, Android version, GPU and exported DRNAS log when reporting failures.

**Preview release — use at your own risk.**
