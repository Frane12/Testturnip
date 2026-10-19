# Blender Hotfix 1.1 r46 — Windows ARM64 Blender on Android

**DRNAS EMU · Experimental Public Pre-release · Android ARM64**

This public preview brings the **Windows ARM64 edition of Blender** to Android through the experimental **DRNAS EMU** compatibility environment. Blender's ARM64 executable runs on ARM64 CPU hardware, while the DRNAS runtime provides Windows API compatibility, Android window/display integration, input handling and access to a user-selected project directory.

**This is not an official Blender Android release, a native Android port of Blender's UI, or a guarantee of compatibility with all phones.** It is a working technical preview for testing and feedback.

> **Tested:** Blender viewport, project/file dialogs, Eevee GPU operation and animation playback on the developer's Adreno 840 test device. Broader compatibility, render quality, frame pacing, and stability still require testing.

## What's new in Hotfix 1.1

- **Draw and drag properly:** hold the left/right mouse button while moving to make continuous brush strokes or drag objects.
- **Easier controls:** bigger, spaced buttons with clear names: Move, Rotate, Scale, Edit Mode and more.
- **Lighter appearance:** buttons are another **10% more transparent**; text stays clear.
- **Automatic graphics setup:** the app detects your GPU and chooses an included driver. No driver selection is needed.
- **Cleaner startup:** launches straight into Blender and fixes the loading screen getting stuck at **92%**.
- **English first:** English is the default; Croatian remains available.
- **Sensible screen size:** Adreno 810 starts at **960 × 544**, other GPUs at **1280 × 720**. You can change it in **Menu → Resolution**; save your project and reopen Blender to apply.
- **File access at startup:** if permission is missing, the app opens Android's All files access setup before you choose your project folder.

The underlying r45 startup fix and controls were tested by the developer on Adreno 840. The r46 permission and opacity changes passed automated regression tests and signed APK verification; wider on-device testing remains necessary.

## GPU support in this APK

**GPU setup is automatic. You do not need to choose or install a driver.** Included drivers are selected only for matching hardware; the app checks Vulkan startup and can fall back if a driver fails that check.

| GPU | Included graphics path | Validation |
| --- | --- | --- |
| **Adreno 840** | NeuroFlow H2.9; H2.8 alternative | **Developer-tested:** Blender viewport, file dialogs, animation and Eevee/Vulkan operation. Complex scenes and ray tracing can still fail. |
| **Adreno 830** | DRNAS S1 Smart; NeuroFlow H2.4 alternative | Included and automatically selected; this Blender hotfix still needs device testing. |
| **Adreno 810** | DRNAS S Ultimate; NeuroFlow H2.7 alternative | Included and automatically selected; this Blender hotfix still needs device testing. Defaults to 960 × 544. |
| **Recognized Adreno 6xx/7xx**, including **720 and 740** | Mesa Turnip R6, Android 9+ | Included for testing. A bundled driver does not guarantee working Blender rendering on every model. |
| **Mali-G52** | Experimental PanVK Kbase r4, Android 12+ | Experimental detection/driver path only; successful Blender GPU rendering is **not confirmed**. Other Mali GPUs are not covered by this PanVK path. |
| **Other GPUs** | Device/system Vulkan where available | No bundled model-specific driver or confirmed Blender compatibility. |

Recognized Adreno 6xx/7xx models: **610, 612, 615, 616, 618, 619, 620, 630, 640, 642, 643, 644, 650, 660, 662, 663, 680, 690, 702, 710, 720, 722, 725, 730, 732, 735, 740, 750**. Detection and the included driver are not a certification that every listed GPU can run every Blender feature. The APK requires Android ARM64; vendor firmware and Vulkan capabilities also matter.

## Download and installation

1. Under **Assets**, download **`Blender-DRNAS-r46-Hotfix-1.1-STABLE-SIGNED.apk`** (approximately 404 MB).
2. Install it on an **Android ARM64** device. Android may require you to allow installation from the app you used to download the APK.
3. Launch the application. If prompted, tap **Open settings**, enable **Allow access to manage all files** for Blender, then return to the app and follow the **folder selection** instructions below. The initial setup may take some time on slower devices.

The app is experimental and requires sufficient storage and available RAM. It does not require root access.

> **Updating from the stable-signed r38–r45 builds:** Install this APK over the existing app; it retains `com.drnas.console`, the same permanent signing certificate and a higher version code (**112**). Keep a separate backup of important projects. Older ephemeral LAB packages may use a different signing identity.

## IMPORTANT — Select your Android project folder at startup

**Blender needs access to an Android folder before it can open and save your own `.blend` files.** The folder you authorize becomes drive **`D:`** inside Blender.

1. **Start Blender DRNAS.** If file permission is missing, tap **Open settings**, enable **Allow access to manage all files**, then go back to Blender. When Android displays the system **folder picker**, browse to the folder where you want to keep your Blender projects.
2. **Select the folder itself**, not an individual `.blend` file. You can use a dedicated folder such as `Documents/BlenderProjects`.
3. Tap **Use this folder** (or the corresponding confirmation button shown by Android), then **Allow** when Android asks you to grant access.
4. Wait for Blender to load. In Blender, choose **File → Open**, navigate to **`D:`** and open the `.blend` project located in your selected folder.
5. To export your project, use **File → Save As** and save it under **`D:`**. The saved files are then accessible to Android in the folder you selected.

**Example:**

| Android | Inside Blender DRNAS |
| --- | --- |
| Selected folder: `Documents/BlenderProjects` | **`D:\`** |
| File: `Documents/BlenderProjects/test.blend` | **`D:\test.blend`** |
| Saved project: `D:\scene.blend` | `Documents/BlenderProjects/scene.blend` |

In this configuration the file browser is intentionally simplified to expose **D:** as the user-facing project drive. **Files outside the folder you approved will not automatically appear there.** If a project does not show up, first confirm that the correct folder was selected, permission was granted and the file is actually inside it.

## Graphics and GPU rendering

The primary verified GPU scenario for this preview is **Eevee on a Qualcomm Adreno 840 test device**. Blender's **Vulkan GPU backend** was exercised during development, including scene rendering. This is *specific on-device evidence*, not a promise of full Vulkan support across all Adreno, Mali or other GPUs.

For an initial GPU test:

1. Open Blender and select **Eevee** in **Render Properties → Render Engine**.
2. Where supported in your Blender build, inspect **Edit → Preferences → System** for the GPU backend and select **Vulkan** if available. A Blender restart may be needed after changing the backend.
3. Start with the default cube or a small, low-complexity project. Try viewport navigation, a short animation and a simple Eevee render.
4. Watch for artifacts, missing objects, application freezes, excessive memory use or unexpected window behavior. If Vulkan fails, record the device and logs before trying alternate settings.

**Important limitation:** Cycles GPU rendering, hardware ray tracing and universal GPU acceleration have **not** been validated by this release. Avoid treating the successful Eevee experiment as proof that all rendering engines and devices are supported.

## Display, touch and performance

The app includes Android touch/input integration and on-screen controls for desktop-oriented interactions. The desktop is still driven by an experimental Windows/Wine/X11 display path, so mouse focus, secondary windows, shortcuts and scaling may not always behave like a native desktop installation.

**r46 technical changes** include more efficient X11 image/request transfer with bounded reusable buffers, fewer unnecessary frame copies and an on-screen FPS indicator. The FPS indicator measures **Android desktop draw callbacks**; it is **not** a Blender render benchmark or a direct Vulkan Present FPS counter. Complex scenes may still render slowly.

## Real device screenshots

These are **genuine screenshots from earlier DRNAS Blender development builds**, not mock-ups or stock Blender promotional images. They illustrate the working Windows ARM64 Blender GUI and file dialog on Android. **They are not screenshots of the final r46 folder picker**; early test builds may show older drive listings or control layouts.

**3D viewport on Android (early development capture):**

![Blender Windows ARM64 3D viewport running in an early DRNAS Android development build](https://raw.githubusercontent.com/Frane12/Testturnip/main/releases/media/blender-development-viewport.webp)

**Blender file-browser/window integration (early development capture):**

![Blender Windows ARM64 file browser within DRNAS on Android; historical development screenshot, not the r46 D-only interface](https://raw.githubusercontent.com/Frane12/Testturnip/main/releases/media/blender-development-file-dialog.webp)

For **r46**, follow the **D: folder mapping** steps above rather than the older disk layout visible in historical screenshots. Device-specific r46 captures of Android folder selection, the D: file view and Eevee rendering are welcome in test reports.

## Known limitations

- **Pre-release quality:** Crashes, stalls, rendering artifacts and incompatible Blender features remain possible.
- **GPU compatibility:** Eevee was exercised on Adreno 840; other models require individual validation.
- **Rendering:** Performance and correctness vary by scene. Ray tracing/Cycles GPU should not be assumed functional.
- **Window management:** Pop-up dialogs and secondary windows may show focus, visibility or positioning issues.
- **File permissions:** Android All files access grants broad shared-storage access. Blender's project drive **D:** maps to your selected folder; the folder picker does not replace the All files access permission.
- **Performance metrics:** The built-in FPS display reports Android UI draw activity, not Blender's render throughput.

## Reporting a problem

Please open an [issue in Testturnip](https://github.com/Frane12/Testturnip/issues) and include your **device model, GPU, Android version, APK revision (r46), Blender settings, exact reproduction steps, logs and screenshots**. For GPU/rendering reports, note the Eevee/Vulkan configuration, scene complexity, resolution, memory behavior and whether the issue reproduces after a clean restart.

## Integrity and credits

- **Release APK:** `Blender-DRNAS-r46-Hotfix-1.1-STABLE-SIGNED.apk`
- **SHA-256:** `27312747b4fa3d588907422e60c6b89def62fa2a41b218c0e10f66352eb20b36`
- **Android application ID:** `com.drnas.console`
- **Project:** DRNAS EMU / EmuExperimental — independent experimental Android integration by Frane12.

**Blender** is developed by the Blender Foundation and contributors. **Wine, Mesa and related compatibility/graphics components** are separate upstream projects with their own authors and licenses. DRNAS EMU is not affiliated with or endorsed by the Blender Foundation, Qualcomm or the upstream projects. Redistribution of upstream components remains subject to their applicable license and source-availability requirements. See [Blender's official licensing information](https://www.blender.org/about/license/) and the [Blender source repository](https://projects.blender.org/blender/blender).

**Release policy:** Experimental, clearly labeled public builds only. This approved public update is **Blender Hotfix 1.1 r46**. Intermediate test builds remain private.
