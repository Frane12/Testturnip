#!/usr/bin/env python3
"""Drnas Turnip A830 V59 LRZ-CLEAN.

Base: Drnas Turnip A830 V2 ADAPTIVE-GMEM.

This is a hardware-specific translation of the portable V58/V59 LRZ ideas to
Snapdragon 8 Elite / Adreno 830.  It deliberately does NOT copy the A810 V57
GMEM/depth/tile thresholds, because A830 has different GMEM capacity, tile
geometry and measured behavior.  The existing A830 V2 measured adaptive-GMEM
learner remains the resource-selection policy.

Ported from A810 V58/V59:
  1) Keep LRZ valid across a fragment-shader LRZ hazard when this A830 draw
     cannot write depth; only the current draw temporarily skips LRZ.
  2) When stencil can kill fragments but depth writes are disabled, do not make
     LRZ write-disable sticky for the whole render pass on A830.

A830-specific cleanup:
  - exact A830 chip gate is evaluated once per LRZ-state calculation and reused;
  - earlier sync/hang, cache-ownership and LRZ-correctness fixes are audited;
  - A810-only PWR_MAX and sampled-depth mechanisms remain A810-only.

No GMEM offsets/allocator, barriers, resolves, MSAA safety, WSI, shader
scheduler, command-buffer synchronization or undocumented registers are changed.
"""
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"A830 V59 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"A830 V59 PASS {label}", flush=True)


# Exact Snapdragon 8 Elite / A830 gate.  Keep the change off other A8XX parts
# so this build is a real A830 translation rather than a generic generation
# experiment.
edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """template <chip CHIP>
static struct __GRAS_LRZ_CNTL
tu6_calculate_lrz_state(struct tu_cmd_buffer *cmd,
                        const uint32_t a)
{""",
    """static bool
frane_a830_v59_lrz_gpu(const struct tu_cmd_buffer *cmd)
{
   if (!cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t id = cmd->device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44050000) ||
          id == UINT64_C(0x44050001) ||
          id == UINT64_C(0xffff44050000);
}

template <chip CHIP>
static struct __GRAS_LRZ_CNTL
tu6_calculate_lrz_state(struct tu_cmd_buffer *cmd,
                        const uint32_t a)
{""",
    "add exact A830 LRZ gate",
)

edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """   VkCompareOp depth_compare_op =
      cmd->vk.dynamic_graphics_state.ds.depth.compare_op;

   struct __GRAS_LRZ_CNTL gras_lrz_cntl = { 0 };""",
    """   VkCompareOp depth_compare_op =
      cmd->vk.dynamic_graphics_state.ds.depth.compare_op;

   /* V59: one exact-device lookup reused by both translated LRZ decisions. */
   const bool frane_a830_v59 = frane_a830_v59_lrz_gpu(cmd);

   struct __GRAS_LRZ_CNTL gras_lrz_cntl = { 0 };""",
    "cache exact A830 LRZ capability once per state calculation",
)

# V58 portable idea, but exact-A830-gated here.
edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """   if (disable_lrz_due_to_fs) {
      if (cmd->state.lrz.prev_direction != TU_LRZ_UNKNOWN || !cmd->state.lrz.gpu_dir_tracking) {
         perf_debug(cmd->device, "Skipping LRZ due to FS");
         temporary_disable_lrz = true;
      } else {
         tu_lrz_invalidate(cmd, "FS writes depth or has side-effects (TODO: fix for gpu-direction-tracking case)");
      }
   }
""",
    """   if (disable_lrz_due_to_fs) {
      /*
       * A830 V59 LRZ-KEEP:
       * If this exact A830 draw cannot write Z, the FS hazard cannot alter the
       * depth buffer or LRZ contents. Keep LRZ valid and only skip LRZ for the
       * current draw. The conservative invalidation remains for real Z writes.
       */
      if ((frane_a830_v59 && !z_write_enable) ||
          cmd->state.lrz.prev_direction != TU_LRZ_UNKNOWN ||
          !cmd->state.lrz.gpu_dir_tracking) {
         perf_debug(cmd->device, "Skipping LRZ due to FS");
         temporary_disable_lrz = true;
      } else {
         tu_lrz_invalidate(cmd, "FS writes depth or has side-effects (TODO: fix for gpu-direction-tracking case)");
      }
   }
""",
    "translate V58 LRZ validity retention to exact A830",
)

# V59 portable idea, exact-A830-gated.
edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """      if (frag_may_be_killed_by_stencil) {
         tu_lrz_disable_write_for_rp(cmd, "Stencil may kill fragments");
      }
""",
    """      if (frag_may_be_killed_by_stencil) {
         /*
          * A830 V59 LRZ-CLEAN:
          * With Z writes disabled, LRZ writes are already disabled for this
          * draw. Avoid making that write-disable sticky for the entire RP on
          * A830; later compatible Z-writing draws may resume LRZ writes.
          * The existing stencil side-effect test below is unchanged.
          */
         if (!frane_a830_v59 || z_write_enable)
            tu_lrz_disable_write_for_rp(cmd, "Stencil may kill fragments");
      }
""",
    "translate V59 non-sticky stencil LRZ rule to exact A830",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip A830 V2 / Mesa ",
    "Drnas Turnip A830 V59 / Mesa ",
    "A830 V59 display identity",
)

# Full active-stack audit: keep A830 V2 resource policy and earlier safety
# fixes, while ensuring no A810-only risky mechanism was retargeted.
lrz = (V / "tu_lrz.cc").read_text()
a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
q = (V / "tu_queue.cc").read_text()
img = (V / "tu_image.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()
pipe = (V / "tu_pipeline.cc").read_text()

for chip in ("0x44050000", "0x44050001", "0xffff44050000"):
    assert chip in lrz, chip

assert "frane_a830_v59_lrz_gpu" in lrz
assert "const bool frane_a830_v59 = frane_a830_v59_lrz_gpu(cmd);" in lrz
assert "(frane_a830_v59 && !z_write_enable)" in lrz
assert "if (!frane_a830_v59 || z_write_enable)" in lrz

# Preserve the A830 V2 measured/tail-aware policy instead of copying A810
# replay/tile thresholds.
for needle in (
    "frane_a830_v2_flags",
    "frane_a830_v2_update_tail",
    "frane_a830_v2_decide",
    'TU_FRANE_A830_BOOST", true',
    'TU_FRANE_A830_LEARN", true',
    "TU_A830_26320_PROFILED_GMEM",
    "TU_A830_26320_SMART_GMEM",
):
    assert needle in a, needle

# Earlier hang/correctness cleanups must survive.
assert "FRANE_2631_POLL_READY" in kg
assert "frane_2631_deadline_ns" in kg
assert "for (uint32_t i = 0; sync = syncobjs[i], i < count; i++)" not in kg
assert "pthread_mutex_unlock(&device->submit_mutex);" in q

# Do not reintroduce the unsafe FS-signature LRZ suppression.
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "same_lrz_signature" not in cmd
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd

# Keep A830's guarded pipeline LRZ optimization and keep risky A810-only
# mechanisms off A830.
assert "TU_A830_26313_LRZ_FASTPATH" in pipe
assert "TU_A810_PWR_MAX" in kg
assert "TU_A830_PWR_MAX" not in kg
assert "TU_A810_SAMPLED_DEPTH_DIAG" in img
assert "TU_A830_SAMPLED_DEPTH_DIAG" not in img

assert "Drnas Turnip A830 V59 / Mesa " in d

print("Drnas Turnip A830 V59 LRZ-CLEAN translated and audited", flush=True)
