# Frane Mesa 26.3.27 A810 GMEM DEPTH STEP 1

Controlled expansion of the confirmed-clean 26.3.26 GMEM-SAFETY policy.

Step 1 re-enables only simple depth-only GMEM attachments. Stencil stays
blocked. Resolve/unresolve, input attachments, feedback loops, MSAA, FDM,
MSRTSS, multiview, layered rendering, conditional load/store and multi-subpass
rendering remain blocked exactly as in 26.3.26.

A/B:
- default: simple depth-only GMEM enabled;
- TU_A810_26327_GMEM_SIMPLE_DEPTH=0 restores the 26.3.26 depth restriction.

Test target: Far Cry 2 benchmark first. If flicker returns, simple depth GMEM is
part of the failing class. If it remains pixel-clean, the next step can expand
one additional class while retaining this known-good boundary.
