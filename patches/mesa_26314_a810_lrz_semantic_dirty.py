#!/usr/bin/env python3
"""Frane Mesa 26.3.14 A810 LRZ-SEMANTIC-DIRTY EXP.

Layered strictly on 26.3.13 LRZ-FASTPATH.

Goal:
Avoid rebuilding the LRZ/depth-plane draw state when Vulkan dynamic state
marks a field dirty but that field is semantically inactive at the current
draw:

- depth-write and depth-compare changes are ignored while depth testing is off;
- stencil-op and stencil-write-mask changes are ignored while stencil testing
  is off.

The enable bits themselves remain LRZ-dirty, so when depth/stencil testing is
enabled later the complete current state is rebuilt before the draw.

A/B:
  TU_A810_26314_LRZ_SEMANTIC_DIRTY=0 -> exact pre-26.3.14 dirty behavior.
  unset / 1                          -> optimized A810-only behavior.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.14 LRZ-SEMANTIC-DIRTY source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.14 LRZ-SEMANTIC-DIRTY PASS {label}", flush=True)


edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """static bool
frane_26313_a810_lrz_fastpath(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == 0x44010000ull || chip == 0xffff44010000ull;
}
""",
    """static bool
frane_26313_a810_lrz_fastpath(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == 0x44010000ull || chip == 0xffff44010000ull;
}

static bool
frane_26314_a810_lrz_semantic_dirty(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26314_LRZ_SEMANTIC_DIRTY", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == 0x44010000ull || chip == 0xffff44010000ull;
}
""",
    "add A810 semantic-dirty gate",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   bool dirty_lrz =
      (dirty & (TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_DISABLE_FS)) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_TEST_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_WRITE_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_BOUNDS_TEST_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_COMPARE_OP) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_STENCIL_TEST_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_STENCIL_OP) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_STENCIL_WRITE_MASK) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_MS_ALPHA_TO_COVERAGE_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_ATTACHMENT_FEEDBACK_LOOP_ENABLE);
""",
    """   bool depth_write_dirty =
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_WRITE_ENABLE);
   bool depth_compare_dirty =
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_COMPARE_OP);
   bool stencil_op_dirty =
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_STENCIL_OP);
   bool stencil_write_mask_dirty =
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_STENCIL_WRITE_MASK);

   if (frane_26314_a810_lrz_semantic_dirty(cmd)) {
      /* These values are not consumed by the effective LRZ/depth state while
       * their parent test is disabled.  The *_TEST_ENABLE bits below remain
       * dirty and force a full rebuild when the parent test becomes active.
       */
      if (!cmd->vk.dynamic_graphics_state.ds.depth.test_enable) {
         depth_write_dirty = false;
         depth_compare_dirty = false;
      }

      if (!cmd->vk.dynamic_graphics_state.ds.stencil.test_enable) {
         stencil_op_dirty = false;
         stencil_write_mask_dirty = false;
      }
   }

   bool dirty_lrz =
      (dirty & (TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_DISABLE_FS)) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_TEST_ENABLE) ||
      depth_write_dirty ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_BOUNDS_TEST_ENABLE) ||
      depth_compare_dirty ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_STENCIL_TEST_ENABLE) ||
      stencil_op_dirty ||
      stencil_write_mask_dirty ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_MS_ALPHA_TO_COVERAGE_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_ATTACHMENT_FEEDBACK_LOOP_ENABLE);
""",
    "filter semantically inactive LRZ dynamic dirty bits",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP / Mesa ",
    "Frane Mesa 26.3.14 A810 LRZ-SEMANTIC-DIRTY EXP / Mesa ",
    "experimental driver identity",
)

cmd = (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
dev = (ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

assert 'TU_A810_26314_LRZ_SEMANTIC_DIRTY' in cmd
assert 'frane_26314_a810_lrz_semantic_dirty' in cmd
assert 'depth_write_dirty = false;' in cmd
assert 'depth_compare_dirty = false;' in cmd
assert 'stencil_op_dirty = false;' in cmd
assert 'stencil_write_mask_dirty = false;' in cmd
assert 'MESA_VK_DYNAMIC_DS_DEPTH_TEST_ENABLE' in cmd
assert 'MESA_VK_DYNAMIC_DS_STENCIL_TEST_ENABLE' in cmd
assert 'TU_A810_26313_LRZ_FASTPATH' in cmd
assert 'TU_A810_26312_DUAL_TEX_PREFETCH' in (
    ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
assert 'TU_A810_26310_UBO_GAP' in (
    ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
assert 'Frane Mesa 26.3.14 A810 LRZ-SEMANTIC-DIRTY EXP' in dev

print("Frane Mesa 26.3.14 A810 LRZ-SEMANTIC-DIRTY EXP applied", flush=True)
