# Frane Turnip — Adreno A830 V20 GMEM Runtime (experimental)

Mesa **26.2.3**, pinned source commit `31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`; Android ARM64 / KGSL.

This branch is derived from **A830 V18 Depth Diagnostic**, not from the
A810 V20 driver. It adds optional WinNative IMapper5 and an A830-specific
real-tile, memory-aware, bounded runtime GMEM/SYSMEM timing policy while
retaining V16 memory/KGSL fixes and V18 depth diagnostics.

See [A830 V20 experiment and testing controls](EXPERIMENT_V20_A830_RUNTIME.md).

## Build and installation

GitHub Actions → **Frane Turnip Mesa 26.2.3 A830 V20 GMEM Runtime**:
download artifact `Frane-Turnip-Mesa-2623-A830-V20-GMEM-RUNTIME`
when the workflow has **successfully** finished. Inside is the matching
Winlator / AdrenoTools ZIP, full applied Mesa source diff, source hashes,
and driver SHA-256. Do **not** install or flash into the system partition.

A successful build is **not** evidence that GMEM artifacts or GPU page faults
are fixed. Test on the A830 device against V18 or a known-good SYSMEM driver.
