## A810 S2.1 Render Recovery — internal bisect candidate

An on-device report showed severe render corruption with S2. This candidate
reverts only the S2 CCU/cache-topology change to the pre-S2 A810 values:
SYSMEM color/depth 64/64 KiB, GMEM color/depth 32/48 KiB, with the original
cache fractions. S2 measured-first GMEM and depth-mode default remain unchanged.
Smart v2, CB1, shader/compiler paths and clock policy remain unchanged.

The cache rollback is the leading hypothesis, not a confirmed root cause.
CPU policy sanitizers and a successful Android build cannot validate GPU
render correctness. Test the same game/scene/settings as the broken S2;
confirm image correctness first, then compare warm benchmark passes.

Keep internal draft until on-device validation. If corruption persists,
next isolate CB and GMEM/LRZ paths rather than adding performance changes.
