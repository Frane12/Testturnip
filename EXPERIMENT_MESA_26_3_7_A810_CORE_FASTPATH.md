# Frane Mesa 26.3.7 A810 CORE-FASTPATH EXP

Based on the successful 26.3.6 A810 AUDIT-FIXES stack and the same pinned Mesa 26.3.0-devel snapshot `eeca16aa41e89a114e53e76439df623c7efb9519`. 26.3.7 is an experimental downstream label, not an official Mesa release.

Changes:
- Adds a 16-slot no-replacement hot render-pass history cache for A810 plain PROFILED mode.
- A repeated cached render pass can bypass the shared mutex and unordered-map lookup in `tu_autotune`.
- Hot histories are permanently pinned until device teardown, so the history reaper cannot invalidate cache pointers.
- Handle release skips the monotonic last-use clock read only for those pinned histories.
- Builds Turnip with ThinLTO to let LLVM optimize across translation units.
- Opt-out for an exact core-fastpath A/B test: `TU_A810_2637_CORE_FASTPATH=0`.

Preserved unchanged:
- 26.3.5 bounded 384-entry RAM-only NIR cache and mixed partial shader-cache behavior.
- 26.3.6 cache-reference lifetime fixes and lazy NIR keys.
- 26.3.4 GMEM runtime policy, V29/26.3.3 PROFILED learning, synchronization and WSI policy.
- IR3 optimizer policy and generated shader logic are intentionally not modified.

Normal setup remains `TU_FRANE_PROFILE_ID=FarCry3` (replace the game name). The new core fastpath is on by default.

Validation includes a multithreaded publication/collision model test, inherited policy/sanitizer tests, full Android ARM64 Turnip compilation and package checks. This is an FPS experiment; no gain is claimed in advance.
