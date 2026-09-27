# Frane Mesa 26.3.14 A810 LRZ-SEMANTIC-DIRTY EXP

Base: exact 26.3.13 A810 LRZ-FASTPATH golden candidate.

This experiment keeps all 26.3.13 LRZ behavior and only reduces redundant
LRZ/depth-plane rebuilds caused by dynamic state that is currently inactive.

Default A810 behavior:
- depth-write / depth-compare dirty bits do not rebuild LRZ while depth test is disabled;
- stencil-op / stencil-write-mask dirty bits do not rebuild LRZ while stencil test is disabled;
- depth/stencil enable bits still force a rebuild, so enabling the test later consumes the complete current state.

A/B control:
- `TU_A810_26314_LRZ_SEMANTIC_DIRTY=1` default
- `TU_A810_26314_LRZ_SEMANTIC_DIRTY=0` exact pre-26.3.14 dirty policy

The experiment is A810-gated and preserves 26.3.13 LRZ fastpath, 26.3.12 dual
texture prefetch, 26.3.10 UBO locality and the earlier core/hotpath stack.
