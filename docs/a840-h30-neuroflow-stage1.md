# DRNAS A840 H3.0 NeuroFlow observer stage1 (2026-10-31)

This isolated branch stages original tracked CPU-only NeuroFlow A840 temporal-observer and optional-work modules, copied without modifications from `experiment/a840-neuroflow-temporal-observer-v01`, into the pinned Mesa 27 Android ARM64 KGSL build. The original reference C tests are run before compilation. `tu_nf_a840_observer_bridge.c` is explicitly added to the Turnip Meson source list and its symbols are checked with readelf.

**Not yet integrated:** the original H2.9 aggressive GMEM/SYSMEM/TEX/A-B-A render policy. That source is not available in the public repository: the published H2.9 driver was a verified ELF binary, not the patch source. This build does not implement the H2.9 logic. No performance gain, NPU inference, active render hooks or dynamic TEX control is claimed.

**Safety:** the observer is not invoked by Mesa's render loop; compilation alone does not enable live optimization or modify Vulkan/GMEM decisions. This stage verifies source portability, linking, tests and a packaged AdrenoTools ZIP. Device rendering and benchmarks remain unverified. Keep original H2.9 and known-working H2.8 for rollback.

**Next gates:** obtain authentic H2.9 source/patches with provenance; port and review individual hunks against the pinned Mesa 27 tree; enable each only under default-off flags; record A840 A/B render screenshots, frametime and Vulkan logs for stock vs `TU_DEBUG=sysmem` before any activation.
