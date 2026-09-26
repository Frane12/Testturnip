# Frane Turnip V28 CLEAN — no A810 GMEM runtime / no MAILBOX override

A/B experiment derived directly from V28 Universal Adaptive.

Removed for A810:
- custom V15-O/Q smart/bounded GMEM runtime participation;
- legacy `TU_A810_GMEM_PROFILE=0` algorithm override;
- A810 flag into the custom BANDWIDTH cost model;
- V23 driver-side MAILBOX/FIFO/RELAXED/IMMEDIATE WSI override.

Retained:
- V28 stable cross-process render-pass identity;
- universal PROFILED SYS/GMEM timing learner;
- V26 weak persistent per-game prior/cache;
- V18 sampled-depth / DiskDVD-related baseline;
- V24 lean profiling fastpath;
- V25 A810 KGSL power experiment;
- ordinary Mesa GMEM layout/safety logic;
- application/DXVK/upstream Mesa WSI present-mode choice.

Recommended A/B variable:
```
TU_FRANE_PROFILE_ID=FC3
```

Do not set `TU_FRANE_PRESENT_MODE` or `TU_A810_GMEM_PROFILE` for this test;
they are intentionally not part of the A810 experiment.
