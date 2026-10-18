# Blender v1.0 r38 — ARM64 Android (DRNAS)

**Experimental public pre-release.** This build packages Blender for Android ARM64 through the DRNAS runtime. It is not an official Blender Android release.

## First launch — select your folder

1. Launch the app and, when prompted, **choose an Android folder** for Blender files using the system folder picker.
2. Grant access to the selected folder. The app exposes it inside Blender/Wine as drive **D:**.
3. In Blender use **File → Open** or **File → Save As** and browse **D:** to open or save projects in that Android folder.
4. To change the accessible folder later, select a different folder through the app's folder-selection flow. Only share a folder you intend the app to use.

## GPU / Eevee status

**Blender Eevee GPU operation was exercised on the tested Adreno Android device.** In Blender's preferences, Vulkan and the Adreno GPU were selected during testing. This is a **device-specific experimental observation**, not a claim of support for every GPU, Cycles GPU rendering, hardware ray tracing, or production-grade stability.

The on-screen FPS HUD measures **Android desktop draw callbacks**, not Blender render-frame throughput or Vulkan presentation FPS.

## Compatibility / testing

- Android ARM64 experimental package; Vulkan/driver compatibility depends on the actual device.
- A valid signed APK is attached below. Android may warn about installation from a source outside the Play Store.
- The package may need substantial storage and RAM; graphics features, saving and complex scenes remain experimental.
- Report your device/GPU, Android version, Blender scene, selected graphics backend, observed FPS/behavior and any crash logs.

**Version:** r38 (initial public Blender v1.0 preview). Future approved builds will use the same Blender v1.0 name with the revision updated.
