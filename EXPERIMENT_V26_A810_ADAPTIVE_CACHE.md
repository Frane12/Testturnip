# Frane Turnip V26 A810 Adaptive Cache

Built on V25 and the V18 sampled-depth reference (Mesa 26.2.3). A810 only.

The existing Mesa PROFILED estimator still decides GMEM versus SYSMEM from GPU timing. V26 increases measurement frequency when the two measured render times are within approximately 12.5%, and samples a loaded profile frequently until both modes have five fresh measurements. It never bypasses render safety or GMEM layout checks.

A profile records only the final SYSMEM selection probability for each render-pass hash after at least 15 measured samples of **each** mode. Mesa's application cache stores an updated four-byte value no more than once per minute per render pass. On a later run, a cached result gives only a weak 35/65 initial preference; both modes are retested. A game identifier and the V26 namespace isolate cache keys; Mesa's own cache namespace isolates driver revisions. Generic DXVK/Wine application names disable persistence unless an explicit game ID is supplied.

Environment variables (restart the container after changes):

- `TU_AUTOTUNE_ALGO=profiled`: use timing-based GMEM/SYSMEM selection.
- `TU_A810_PROFILE_CACHE=0`: disable loading and saving profiles.
- `TU_A810_PROFILE_ID=fc3`: choose a unique stable identifier per game, particularly if DXVK reports a generic Vulkan application name. Set a different value for each game.
- `TU_A810_PROFILED_SAMPLE_INTERVAL=4`: compare the V24 default against V25/V26 default 8 when sufficiently confident.
- `TU_A810_PWR_MAX=0`: disable the V25 KGSL maximum-power request for a controlled comparison.

This is an experimental build. Profile persistence depends on Mesa's disk cache being enabled and writable in the container. The cache stores a render-pass preference, not FPS, RAM usage, thermal state, or scene-specific statistics. Repeated in-game runs are needed to establish a performance benefit.
