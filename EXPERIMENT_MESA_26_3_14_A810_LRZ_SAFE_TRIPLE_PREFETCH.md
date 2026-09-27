# Frane Mesa 26.3.14 A810 LRZ-SAFE + TRIPLE-PREFETCH EXP

Layered directly on 26.3.13.

## LRZ correctness fix

The 26.3.13 fragment-shader signature optimization is removed.

26.3.14 restores the upstream Turnip rule in `tu_bind_fs()`: whenever the
fragment shader really changes, both `TU_CMD_DIRTY_LRZ` and
`TU_CMD_DIRTY_FS` are set.

This specifically targets the one-frame vegetation/depth corruption observed
in FC3 with the Vulkan renderer. The 26.3.13 sparse/undefined color-attachment
LRZ classification is retained because it does not skip the LRZ state-machine
update on shader changes.

## Small independent experiment: third guarded texture prefetch

The default remains the already-tested 26.3.12 behavior: at most **two** legal
A810 fragment texture prefetches.

To test one extra pre-dispatch fetch:

`TU_A810_26314_TRIPLE_TEX_PREFETCH=1`

This raises the cap from 2 to 3 only inside the existing 26.3.11 restricted
path. Bindless remains rejected and the public A810
`has_fs_tex_prefetch` capability remains disabled.

Disable / baseline:

`TU_A810_26314_TRIPLE_TEX_PREFETCH=0`

The variable defaults to 0.

## Recommended test order

1. First run FC3 with **no new variable**. Confirm the one-frame vegetation /
   depth corruption is gone.
2. Record FPS and frametime in the same scene.
3. Then enable `TU_A810_26314_TRIPLE_TEX_PREFETCH=1`.
4. Repeat the identical route and watch for:
   - low-FPS floor;
   - shader-transition stutter;
   - high-FPS peaks;
   - texture corruption or missing samples;
   - compile-time regressions or GPU hangs.

This separation is intentional: LRZ correctness is tested first, then the
prefetch experiment is isolated.
