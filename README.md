# Testturnip — experimental Android Turnip build

Build target: Mesa **26.1.4** (commit `6dfbc555b4128ee51139c5f78c5aba2594c9701b`), Android arm64, KGSL.

## Build

Open **Actions → Build Turnip Android → Run workflow**. On success, download the `turnip-mesa-26.1.4-android-arm64` artifact. It contains `libvulkan_freedreno.so` and `meta.json`, packaged in a ZIP for testing in compatible driver loaders.

This is a baseline upstream build, **not** a verified A810/A830-specific GMEM optimization. A build success does not establish device compatibility, stability, or improved FPS/RAM. Test with a known-good driver available for rollback. Do not flash the system vendor partition.

The workflow checks out an exact upstream Mesa commit, configures Meson for Android arm64/KGSL, and only publishes an artifact after the shared library is produced. Build logs are available in Actions.
