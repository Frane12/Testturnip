# DRNAS FreeCAD / Proton 11 — public GitHub Actions runner LAB

This **public CI runner** builds an isolated Android test APK from the **pinned private** `Frane12/EmuExperimental` source. Private code, Git history, signing keys, and source archives are **never committed to this public repository**. The build uses the existing scoped `EMUEXPERIMENTAL_RELEASE_READ_TOKEN` GitHub Actions secret only for a temporary checkout, with persisted checkout credentials disabled.

- Target: DRNAS Android Wine/Proton 11 + FEX Windows x64 compatibility and OpenGL testing.
- Android APK: separate FreeCAD LAB debug application ID; **not** an upgrade to Blender or DRNAS Console. Debug signing is intentionally non-stable.
- FreeCAD itself: **not included**. Install an official **Windows x64** FreeCAD executable manually in the Wine C: drive, then open `Shortcuts → FreeCAD (LAB)` and confirm launch. A Linux ARM64 AppImage is not a Wine executable.
- Build output: **GitHub draft release only**, named for the runner. It must not be promoted to a public binary release without licensing and privacy review. Its APK is not tested on an actual Android device.
- The public runner never builds Blender or modifies the existing native FreeCAD OCCT build. The native path remains at [DRNAS-Native-FreeCAD](https://github.com/Frane12/DRNAS-Native-FreeCAD).
- A GitHub Actions green check verifies **APK packaging**, not that FreeCAD's GUI, 3D viewport, STEP or save/load already work. The Windows x64 translation and OpenGL paths must be checked on a phone.

## Security and build boundaries

The build retrieves the **exact pinned private commit**, then uses the same FreeCAD Proton 11 LAB packaging and checks found in that commit. A read-only GitHub token is used for checkout. No stable private signing material is loaded or exported. No `private-src` files go to release assets or artifacts. Public runner logs may include build diagnostics; inspect them before sharing externally.

Source code from the private emulator is deliberately not copied into this public branch. This repo contains only the workflow and these notes. The resulting APK contains bundled upstream open-source compatibility components and a binary DRNAS emulator build; respect third-party licenses before publishing further.

**Workflow:** [FreeCAD Proton 11 PUBLIC runner](../../.github/workflows/freecad-proton11-public-runner.yml).
