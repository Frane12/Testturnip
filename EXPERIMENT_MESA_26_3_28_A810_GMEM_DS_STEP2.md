# Frane Mesa 26.3.28 A810 GMEM DEPTH/STENCIL STEP 2

Controlled expansion of the confirmed-clean 26.3.27 policy.

Step 2 re-enables simple combined depth+stencil GMEM attachments while all
resolve/unresolve, feedback, input attachment, MSAA, FDM, MSRTSS, multiview,
layered, partial-render-area and multi-subpass cases remain blocked.

This is aimed at common D24S8/D32S8-style passes used by older D3D games.

A/B:
- default: simple combined depth+stencil GMEM enabled;
- TU_A810_26328_GMEM_SIMPLE_DS=0 restores 26.3.27 behavior.

Test Far Cry 2 benchmark first. If flicker returns, the combined DS path is in
the failing class. If clean, we have eliminated both ordinary depth and simple
depth+stencil as root causes and can move next to resolve/load-store complexity.
