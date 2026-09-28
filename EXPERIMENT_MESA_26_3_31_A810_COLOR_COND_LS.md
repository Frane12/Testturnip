# Frane Mesa 26.3.31 A810 COLOR CONDITIONAL LOAD/STORE

Performance-oriented next penetration step after the confirmed-clean A810
phone tests.

This build opens exactly one new GMEM class:
- conditional load/store is allowed only for color attachments.

Still blocked:
- conditional depth/stencil;
- resolves/unresolves;
- MSAA;
- input attachments;
- feedback loops;
- multiview/FDM/MSRTSS;
- layered/partial/multi-subpass cases.

A/B:
- TU_A810_26331_GMEM_COLOR_COND_LS=1 (default)
- TU_A810_26331_GMEM_COLOR_COND_LS=0 restores 26.3.30 behavior

For the phone performance path, packed DS can still be independently toggled
with TU_A810_26330_GMEM_PACKED_DS=1.
