# Frane Mesa 26.3.32 A810 GMEM PERFORMANCE BASELINE

This build consolidates the combinations that have tested well before moving
on to GMEM allocation/packing work.

Enabled by default:
- simple depth GMEM;
- simple combined depth+stencil GMEM;
- packed depth/stencil GMEM;
- simple color conditional load/store.

Still conservative:
- stencil load/store split path remains off;
- depth/stencil conditional load/store remains SYSMEM;
- resolves/unresolves remain blocked;
- MSAA remains blocked;
- input attachments and feedback loops remain blocked;
- multiview/FDM/MSRTSS/layered/partial/multi-subpass cases remain blocked.

The next development direction after validating this baseline is GMEM
organization itself: attachment packing, ordering, tile footprint and
fragmentation pressure, rather than opening additional risky render-pass
classes.
