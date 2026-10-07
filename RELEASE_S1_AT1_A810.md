# Drnas-Turnip S1 AT1 A810 — experimental draft

**Base:** public Drnas-Turnip S1 A810 source commit  
**Target:** Adreno 810 · Android ARM64 / KGSL  
**Status:** experimental draft / A-B test

AT1 is a different autotuner direction built directly on S1. It deliberately
does not carry the later MH1 or KP1 experiments.

The policy keeps Mesa PROFILED live and adds contextual workload catalogs,
robust timing statistics, change detection and sparse adaptive exploration.

### What to test

Run the same Crysis GPU TimeDemo for three passes first, then use at least one
real game with scene changes. Compare average FPS, repeated minimum, frametime
feel and whether performance drifts after transitions.

For a same-binary control test set:

`TU_FRANE_AT1=0`

That disables only AT1 and falls back to the S1 policy.
