# Frane Mesa 26.3.29 A810 STENCIL LOAD/STORE BISECT

26.3.27 is confirmed clean on the tablet. 26.3.28 increases performance but
reintroduces rare flicker on the tablet, while the same 26.3.28 build is clean
on the phone with the same A810 SoC.

This build keeps combined depth+stencil GMEM enabled but splits stencil
load/store into its own A/B switch.

Default:
- TU_A810_26329_GMEM_STENCIL_LOADSTORE=0
- combined DS without stencil load/store may remain GMEM;
- any GMEM pass needing stencil load or store falls back to SYSMEM.

A/B:
- 0 = new safe split
- 1 = V28-like stencil load/store allowed

Interpretation:
- tablet clean at 0 and flickers at 1: stencil load/store path isolated;
- tablet flickers at both: combined DS itself remains suspect;
- phone clean at both: reinforces platform/kernel/firmware-specific sensitivity.

All other 26.3.26 safety guards remain intact.
