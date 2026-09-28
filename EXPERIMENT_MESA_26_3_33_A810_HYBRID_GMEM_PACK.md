# Frane Mesa 26.3.33 A810 HYBRID GMEM PACK

26.3.32 remains the known-good performance baseline. This build does not open
any additional render-pass class. It changes only how GMEM blocks are divided
between already-allowed attachments.

Mesa upstream currently uses a proportional greedy allocator and even carries
a TODO noting a mixed-cpp counterexample:

- cpp {1, 4}
- upstream: blocks {12, 52} -> 196608 common pixels
- optimal: blocks {13, 51} -> 208896 common pixels

26.3.33 adds an A810-only hybrid allocator:

1. calculate the exact upstream greedy layout;
2. calculate a balanced max-min layout with a binary search over common pixel
   capacity while respecting every allocation's block alignment;
3. use the balanced layout only if it strictly increases pass->gmem_pixels;
4. otherwise keep the upstream offsets and block split unchanged.

This makes the experiment conservative: equal-result cases are byte-for-byte
the old packing path, while heterogeneous attachment layouts can use otherwise
wasted GMEM more effectively.

A/B:

- TU_A810_26333_GMEM_HYBRID_PACK=1 (default)
- TU_A810_26333_GMEM_HYBRID_PACK=0 (upstream greedy packing)

The next step, if this validates well, is to combine packing efficiency with
tile-shape / attachment-lifetime organization rather than simply opening more
GMEM render-pass cases.
