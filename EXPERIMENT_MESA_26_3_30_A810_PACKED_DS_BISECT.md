# Frane Mesa 26.3.30 A810 PACKED DEPTH/STENCIL BISECT

Observed hardware matrix:
- 26.3.27 depth-only GMEM: tablet clean.
- 26.3.28/29 combined DS: tablet flickers, phone clean.
- 26.3.29 stencil load/store A/B does not remove tablet flicker.

Mesa's render-pass attachment fields explicitly describe load_stencil/store_stencil
as the D32S8 separate-stencil case. The A8xx Z/S emission also programs a
separate stencil GMEM base only for D32_SFLOAT_S8_UINT (and pure S8). Therefore
a packed D24S8-style pass can bypass the V29 distinction entirely.

26.3.30 splits the hardware paths:
- default TU_A810_26330_GMEM_PACKED_DS=0: packed DS -> SYSMEM;
- TU_A810_26330_GMEM_PACKED_DS=1: re-enable packed DS GMEM (V29-like);
- D32S8 separate-stencil path remains under the previous safety guards.

Interpretation:
- tablet clean at 0, flickers at 1 => packed DS GMEM path isolated;
- flickers at both => investigate separate D32S8 / tile-edge / CCU state next;
- phone clean at both => platform-specific sensitivity remains supported.
