# Frane Mesa 26.3.3 A810 PROFILE-TURBO EXP

**Experimental downstream name, not an official Mesa release.**

Baseline: green **Frane Mesa 26.3.2 A810 TURBO EXP**.

This branch is tuned for the user's current workflow: the only recommended
runtime variable is the per-game profile identity, for example
`TU_FRANE_PROFILE_ID=FarCry3`.

Changes over 26.3.2:

- Persistent game-profile warm start confirms at 1/4 cadence instead of 1/2.
- Close GMEM/SYSMEM races still measure aggressively at 1/2.
- Mild winner: 1/8; clear winner: 1/16; dominant winner: 1/32.
- PROFILED random selection no longer performs a relaxed atomic fetch-add per
  decision; it uses a thread-local mixed decision stream keyed by render-pass.
- Autotune housekeeping moves from 1/128 to 1/256 submits.
- Accepted A810 PWR_MAX refresh moves from 1/1024 to 1/4096 submits.
- KGSL WAIT_ANY uses a 16-entry stack buffer; common small wait sets no longer
  allocate/free heap memory.
- Large WAIT_ANY sets retain a heap fallback.
- Timestamp-fence conversion failures now abort cleanly with DEVICE_LOST and
  close already-owned fence FDs.

All 26.3.1/26.3.2 sync correctness fixes are retained. No new GMEM layout,
shader, WSI, descriptor-prefetch or neural/AI experiment is added.
