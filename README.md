# Frane Turnip V25 — A810 Power Perf (experimental)

Pinned Mesa 26.2.3, commit
`31e9a6b2e95e30d84bf3177d1f497d063e59b6b2`, real Android
ARM64/KGSL Turnip for Winlator/Bannerlator X11. Forked from V24.
Our V18, V22, V23 and V24 reference branches remain unmodified.

V25 adds an **A810-only, queue-scoped KGSL PWR_MAX request**, with
original context-creation fallback if the kernel rejects the flag.
Does not disable thermal protection. Confident preferred PROFILED render
passes sample 1 in 8 by default (V24: 1 in 4); uncertain paths measure
as before. DiskDVD shader workaround and GPU register values are unchanged.
Qualcomm binary ZIP audit: [experiment notes](EXPERIMENT_V25_A810_POWER_PERF.md).

## A/B toggles

`TU_A810_PWR_MAX=0`: original V24 clock-management policy.

`TU_A810_PROFILED_SAMPLE_INTERVAL=4`: original V24 sampling policy.

`TU_A810_V24_FASTPATH=0`: original V23 CPU hotpath.

`TU_FRANE_PRESENT_MODE=off`: original app-defined Vulkan presentation.

**No guaranteed FPS boost:** kernel clocks/thermals may limit the effect.

## Driver

GitHub Actions builds `Frane-Turnip-Mesa-2623-A810-V25-POWER-PERF.zip`.
Only use the ZIP after its ARM64 build succeeds; a source branch by itself
is not an installable driver. GitHub release tag `v25-a810-power-perf`.
Never flash system/vendor files.
