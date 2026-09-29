#!/usr/bin/env python3
"""Turnip A810 V42 CLEAN-DRAW-V2.

Layered strictly on V41, which itself is layered on the V39 golden baseline.

V41 proved a useful direction but its cache invalidation was intentionally too
broad: TU_CMD_DIRTY_VS_PARAMS (and unrelated state such as descriptors/VBs)
can be set on ordinary draws, causing the cached values to be rebuilt almost
as often as the original code.

V42 keeps the exact V41 cached values but narrows invalidation to the state that
can actually change each result.  It also resolves the A810/env gate once per
command buffer and removes redundant gate checks from the hot consume path.

No GMEM/SYSMEM policy, LRZ, barrier, shader, descriptor or rendering semantics
are changed.
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
            f"V42 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V42 PASS {label}", flush=True)


edit(
    "src/freedreno/vulkan/tu_cmd_buffer.h",
    """   uint32_t frane_26341_initiator_base;
   uint32_t frane_26341_draw_bandwidth;
   bool frane_26341_initiator_valid;
   bool frane_26341_bandwidth_valid;
""",
    """   uint32_t frane_26341_initiator_base;
   uint32_t frane_26341_draw_bandwidth;
   bool frane_26341_initiator_valid;
   bool frane_26341_bandwidth_valid;

   /* V42: resolved gates + one dependency not represented by tu_cmd_dirty_bits. */
   uint8_t frane_26342_initiator_mode;
   uint8_t frane_26342_bandwidth_mode;
   uint8_t frane_26342_cached_index_size;
""",
    "add resolved hotpath gate state",
)

anchor = """static uint32_t
frane_26341_build_initiator_base(struct tu_cmd_buffer *cmd)
"""

helpers = r'''static inline bool
frane_26342_initiator_enabled(struct tu_cmd_buffer *cmd)
{
   /* 0 = unresolved, 1 = disabled/non-A810, 2 = enabled A810. */
   if (unlikely(cmd->state.frane_26342_initiator_mode == 0)) {
      cmd->state.frane_26342_initiator_mode =
         frane_26341_initiator_cache_enabled(cmd) ? 2 : 1;
   }

   return cmd->state.frane_26342_initiator_mode == 2;
}

static inline bool
frane_26342_bandwidth_enabled(struct tu_cmd_buffer *cmd)
{
   if (unlikely(cmd->state.frane_26342_bandwidth_mode == 0)) {
      cmd->state.frane_26342_bandwidth_mode =
         frane_26341_bandwidth_cache_enabled(cmd) ? 2 : 1;
   }

   return cmd->state.frane_26342_bandwidth_mode == 2;
}

static bool
frane_26342_initiator_dynamic_dirty(const struct tu_cmd_buffer *cmd)
{
   if (BITSET_IS_EMPTY(cmd->vk.dynamic_graphics_state.dirty))
      return false;

   return BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                      MESA_VK_DYNAMIC_IA_PRIMITIVE_TOPOLOGY) ||
          BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                      MESA_VK_DYNAMIC_TS_PATCH_CONTROL_POINTS);
}

static bool
frane_26342_bandwidth_dynamic_dirty(const struct tu_cmd_buffer *cmd)
{
   if (BITSET_IS_EMPTY(cmd->vk.dynamic_graphics_state.dirty))
      return false;

   return
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_CB_LOGIC_OP_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_CB_LOGIC_OP) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_CB_ATTACHMENT_COUNT) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_CB_COLOR_WRITE_ENABLES) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_CB_BLEND_ENABLES) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_CB_WRITE_MASKS) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_TEST_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_DEPTH_WRITE_ENABLE) ||
      BITSET_TEST(cmd->vk.dynamic_graphics_state.dirty,
                  MESA_VK_DYNAMIC_DS_STENCIL_TEST_ENABLE);
}

static uint32_t
frane_26341_build_initiator_base(struct tu_cmd_buffer *cmd)
'''

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    anchor,
    helpers,
    "add V42 selective invalidation/gate helpers",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   const bool frane_26341_graphics_dirty =
      !BITSET_IS_EMPTY(cmd->vk.dynamic_graphics_state.dirty) ||
      (cmd->state.dirty & ~TU_CMD_DIRTY_COMPUTE_DESC_SETS);

   uint32_t dynamic_draw_state_dirty = 0;
   if (frane_26341_graphics_dirty) {
      dynamic_draw_state_dirty = tu_emit_draw_state<CHIP>(cmd);
   }
""",
    """   const bool frane_26341_graphics_dirty =
      !BITSET_IS_EMPTY(cmd->vk.dynamic_graphics_state.dirty) ||
      (cmd->state.dirty & ~TU_CMD_DIRTY_COMPUTE_DESC_SETS);

   /* V42 snapshots only dependencies of each derived cache before
    * tu_emit_draw_state() consumes/clears the dirty state.  In particular,
    * VS_PARAMS, descriptors and ordinary vertex-buffer churn no longer force
    * either cache to rebuild.
    */
   const bool frane_26342_initiator_dirty =
      (cmd->state.dirty &
       (TU_CMD_DIRTY_PROGRAM | TU_CMD_DIRTY_TES |
        TU_CMD_DIRTY_TCS | TU_CMD_DIRTY_DRAW_STATE)) ||
      frane_26342_initiator_dynamic_dirty(cmd) ||
      (cmd->state.frane_26341_initiator_valid &&
       cmd->state.frane_26342_cached_index_size != cmd->state.index_size);

   const bool frane_26342_bandwidth_dirty =
      (cmd->state.dirty &
       (TU_CMD_DIRTY_PROGRAM | TU_CMD_DIRTY_SUBPASS |
        TU_CMD_DIRTY_DRAW_STATE)) ||
      frane_26342_bandwidth_dynamic_dirty(cmd);

   uint32_t dynamic_draw_state_dirty = 0;
   if (frane_26341_graphics_dirty) {
      dynamic_draw_state_dirty = tu_emit_draw_state<CHIP>(cmd);
   }
""",
    "snapshot only cache-relevant dirty state",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (frane_26341_initiator_cache_enabled(cmd) &&
       (!cmd->state.frane_26341_initiator_valid ||
        frane_26341_graphics_dirty)) {
      cmd->state.frane_26341_initiator_base =
         frane_26341_build_initiator_base(cmd);
      cmd->state.frane_26341_initiator_valid = true;
   }

   if (frane_26341_bandwidth_cache_enabled(cmd) &&
       (!cmd->state.frane_26341_bandwidth_valid ||
        frane_26341_graphics_dirty)) {
      cmd->state.frane_26341_draw_bandwidth =
         frane_26341_calc_draw_bandwidth(cmd);
      cmd->state.frane_26341_bandwidth_valid = true;
   }
""",
    """   if (frane_26342_initiator_enabled(cmd) &&
       (!cmd->state.frane_26341_initiator_valid ||
        frane_26342_initiator_dirty)) {
      cmd->state.frane_26341_initiator_base =
         frane_26341_build_initiator_base(cmd);
      cmd->state.frane_26342_cached_index_size = cmd->state.index_size;
      cmd->state.frane_26341_initiator_valid = true;
   }

   if (frane_26342_bandwidth_enabled(cmd) &&
       (!cmd->state.frane_26341_bandwidth_valid ||
        frane_26342_bandwidth_dirty)) {
      cmd->state.frane_26341_draw_bandwidth =
         frane_26341_calc_draw_bandwidth(cmd);
      cmd->state.frane_26341_bandwidth_valid = true;
   }
""",
    "narrow cache rebuild conditions",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (frane_26341_bandwidth_cache_enabled(cmd) &&
       cmd->state.frane_26341_bandwidth_valid) {
""",
    """   if (cmd->state.frane_26341_bandwidth_valid) {
""",
    "remove repeated bandwidth gate from consume path",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (frane_26341_initiator_cache_enabled(cmd) &&
       cmd->state.frane_26341_initiator_valid) {
""",
    """   if (cmd->state.frane_26341_initiator_valid) {
""",
    "remove repeated initiator gate from consume path",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Turnip A810 V41 / Mesa ",
    "Drnas Turnip V42 / Mesa ",
    "V42 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
hdr = (V / "tu_cmd_buffer.h").read_text()
dev = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()

for needle in (
    "frane_26342_initiator_enabled",
    "frane_26342_bandwidth_enabled",
    "frane_26342_initiator_dynamic_dirty",
    "frane_26342_bandwidth_dynamic_dirty",
    "MESA_VK_DYNAMIC_IA_PRIMITIVE_TOPOLOGY",
    "MESA_VK_DYNAMIC_CB_WRITE_MASKS",
    "MESA_VK_DYNAMIC_DS_DEPTH_TEST_ENABLE",
    "VS_PARAMS, descriptors",
):
    assert needle in cmd, needle

for needle in (
    "frane_26342_initiator_mode",
    "frane_26342_bandwidth_mode",
    "frane_26342_cached_index_size",
):
    assert needle in hdr, needle

# V41 fallback code and V39 golden correctness/policy remain present.
assert 'TU_A810_26341_INITIATOR_CACHE", true' in cmd
assert 'TU_A810_26341_BANDWIDTH_CACHE", true' in cmd
assert "frane_26341_build_initiator_base" in cmd
assert "frane_26341_calc_draw_bandwidth" in cmd
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert "Drnas Turnip V42 / Mesa " in dev

print("Drnas Turnip V42 CLEAN-DRAW-V2 applied", flush=True)
