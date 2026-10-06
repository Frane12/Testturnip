# S2.4 KP1 — A810 KGSL PWR_MAX

This experiment starts from the S2.3 Q2 source baseline and deliberately leaves
its render-pass, SMART-GMEM, Q2, LRZ and shader scheduling policies unchanged.

KP1 changes direction to the Qualcomm KGSL kernel interface:

- request `KGSL_CONTEXT_PWR_CONSTRAINT` for the A810 context;
- request `KGSL_PROP_PWR_CONSTRAINT` with `KGSL_CONSTRAINT_PWR_MAX` after
  queue creation;
- set `KGSL_CMDBATCH_PWR_CONSTRAINT` on normal GPU command submissions;
- re-assert PWR_MAX every 1000 normal submissions;
- `TU_FRANE_KGSL_PWRMAX=0` is the A/B rollback switch.

The intent is higher and more stable GPU clock residency, not a new GMEM
heuristic. This may raise power draw and temperature, so benchmark with the
same cooling/performance-mode conditions as the S2.3 Q2 reference.
