# Drnas Turnip — experimental A810 Turnip work

Public development repository for our Android **Adreno 810 / Turnip** experiments.

The current work tracks upstream Mesa/Turnip and focuses on measured GMEM/SYSMEM policy, GMEM allocation/search, depth handling, LRZ-safe behavior, concurrent binning, shader/pipeline efficiency and Winlator-oriented testing.

## Public milestone builds

To keep the Releases page readable, only milestone/reference builds are meant to stay public:

- **V39 — GMEM-PRESSURE**: stronger future-aware GMEM search/pressure bound.
- **V47 — CB-PROFILER**: concurrent-binning profiling/control milestone.
- **V52 — CLEAN-INTERFACE**: standardized short `TU_FRANE_*` test controls.
- **V54 — UPPER-PROBE**: preserved reference build for the current Crysis depth/GMEM work.
- **V56 — GMEM-HARD-PUSH**: current aggressive measured GMEM boundary experiment.

Intermediate builds are development probes. Their public Release entries may be removed once they have answered the question they were built for. The source branches/commit history are kept for development and comparison.

## Testing

These are experimental Android ARM64 KGSL drivers, not general-purpose stable releases. Use a known-good driver as rollback and compare builds under the same game, scene, resolution, DXVK/Wine/Proton setup and benchmark pass count.

For the current A810 work, environment controls use the short `TU_FRANE_*` namespace. Experimental defaults are normally baked into the test build so the first benchmark run should be done **without extra variables** unless the release notes say otherwise.

## Scope

The project does not modify the Android vendor partition. Builds are packaged for compatible userspace driver loaders such as AdrenoTools/Winlator-style setups.
