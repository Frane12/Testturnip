# Frane Mesa 26.3.23 A810 UPSTREAM-AUDIT EXP

Android ARM64/KGSL Turnip for Winlator/AdrenoTools based on Mesa 26.3.0-devel,
upstream eda9aceb39d5ff169b096444abe366bdf2269e24.
26.3.23 is a downstream build label, not an official Mesa release.

Preserves the 26.3.22 A810 stack, isolates shader caches by custom compiler
settings and removes duplicate SMART-GMEM cost evaluation.
See [changes and tests](EXPERIMENT_MESA_26_3_23_A810_UPSTREAM_AUDIT.md).

Actions produces Frane-Mesa-26.3.23-A810-UPSTREAM-AUDIT-EXP.zip with source
provenance, complete applied patch and checksums. Install after a successful
Android compilation. No hardware/FPS result is claimed.
