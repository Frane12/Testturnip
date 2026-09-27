# Frane Mesa 26.3.6 A810 AUDIT-FIXES

Based on the successful 26.3.5 A810 SHADER-PIPELINE EXP, Mesa 26.3.0-devel eeca16aa41e89a114e53e76439df623c7efb9519. 26.3.6 is the downstream experiment label, not an official Mesa version.

Changes:
- Release all borrowed shader-cache references on VK_PIPELINE_COMPILE_REQUIRED, including hits after a miss.
- Calculate intermediate NIR keys only after the compiled cache misses and compilation is permitted.
- Round positive remaining KGSL wait time upward to milliseconds instead of truncating absolute timestamps.
- Remove an unused NIR hit local.

Preserved: 384-entry RAM-only NIR cache, full-stage lookup, shader optimizer, GMEM runtime, autotuner thresholds, power policy and presentation behavior. No LRU/cache size experiment in this build.

Normal setup: TU_FRANE_PROFILE_ID=FarCry3 (replace game name). Optional previous controls remain available.

Validation: source-extracted mixed-cache ownership regression, timeout edge tests, inherited host policy/sanitizer tests, Android ARM64 compile and ELF/ZIP checks in Actions. Device performance and GPU stability still require A810 testing. No FPS gain is claimed in advance.
