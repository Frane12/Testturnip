# Blender PrefixFix LAB r61 — ARM64 Android (experimental tester build)

**Early experimental test build — not an official Blender release, and not a tested compatibility guarantee.**

This is a **separate, side-by-side Android app** (`com.drnas.console.prefixfixlab`) intended for reproducing and testing Wine-prefix initialization problems without replacing the installed Blender v1.1 app.

## Changes under test

- Serialize Wine-prefix creation to prevent two simultaneous initialization attempts.
- Preserve an existing incomplete prefix as a backup rather than delete it.
- Create the replacement prefix in temporary storage and commit only after staging succeeds.
- Reject existing prefix symlinks and preserve existing data on extraction failure.
- Include prefix-recovery regression tests. No changes to Blender rendering, input, Vulkan or GPU drivers.

## Important limitations

- **This LAB does not repair the installed public Blender's app data**, because it has a different Android package ID. It exercises the recovery code only inside its own sandbox.
- Samsung Galaxy A33 / Exynos 1280 compatibility is **not yet confirmed**. Prefix recovery and GPU rendering are separate issues.
- Users should preserve backups of their projects and share diagnostic logs if installation still fails.
- Requires Android on an ARM64 device and substantial free storage for the embedded runtime.

Source APK was built and permanently signed in the private EmuExperimental repository; only the selected APK and a checksum are copied here after byte-for-byte SHA-256 verification.

**SHA-256:** `d945f07162c9cbcd595b7084559abb5d598d98399decc97257ab61078d112988`
