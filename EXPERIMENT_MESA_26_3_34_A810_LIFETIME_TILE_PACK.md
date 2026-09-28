# Frane Mesa 26.3.34 A810 LIFETIME-TILE-PACK

26.3.33 remains the known-good baseline. This experiment keeps every V33
safety gate and the hybrid max-min GMEM packer unchanged.

The new part targets attachment lifetime reuse. Upstream Turnip can already
alias non-overlapping attachment lifetimes, but its exact-cpp/closest-cpp
selection may merge an allocation across a large unused subpass gap and then
prevent a later attachment from reusing that region.

26.3.34 therefore builds a second candidate allocation graph in parallel:

1. reuse remains legal only for non-overlapping subpass lifetimes;
2. the backing allocation cpp must be at least the attachment cpp;
3. candidates are scored by incremental lifetime*cpp waste:
   gap * allocation_cpp + cpp_slack * attachment_span;
4. the candidate graph is packed with the same V33 greedy + max-min hybrid
   policy;
5. the candidate offsets are adopted only if they strictly increase
   pass->gmem_pixels for that GMEM layout.

That last rule is the key safety property: equal or worse candidate layouts
fall back to the exact V33 offsets. The optimization therefore changes tile
capacity only when it can prove a larger GMEM pixel budget for the pass.

A/B:

- TU_A810_26334_GMEM_LIFETIME_TILE_PACK=1 (default)
- TU_A810_26334_GMEM_LIFETIME_TILE_PACK=0 (exact V33 behavior)

No resolve/MSAA/feedback/input-attachment safety class is newly opened by this
build, and packed depth+stencil remains at the validated 26.3.32/26.3.33 policy.
