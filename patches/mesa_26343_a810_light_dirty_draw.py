#!/usr/bin/env python3
"""Drnas Turnip V43 LIGHT-DIRTY-DRAW.

Layered on V42/V39.  V42 removed broad invalidation from the draw initiator
and bandwidth caches.  V43 targets the next common CPU-side case: draws where
the only pending graphics work is an already-built vertex-buffer and/or
VS-parameter draw state.

For those exact states the normal tu6_draw_common() tail walks a long series of
unrelated dirty-state tests before eventually emitting only one or two
CP_SET_DRAW_STATE entries.  V43 recognizes that equivalence class and jumps
straight to the same packet emission.

The fast path is intentionally narrow:
  * A810 only;
  * no dynamic draw-state emission from tu_emit_draw_state();
  * dynamic graphics dirty bitset must be empty;
  * the only graphics dirty bits may be TU_CMD_DIRTY_VERTEX_BUFFERS and/or
    TU_CMD_DIRTY_VS_PARAMS;
  * compute descriptor dirtiness is preserved exactly as before.

A/B:
  TU_A810_26343_LIGHT_DIRTY_DRAW=0
restores the V42 tail for this case.
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
            f"V43 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V43 PASS {label}", flush=True)


edit(
    "src/freedreno/vulkan/tu_cmd_buffer.h",
    """   uint8_t frane_26342_initiator_mode;
   uint8_t frane_26342_bandwidth_mode;
   uint8_t frane_26342_cached_index_size;
""",
    """   uint8_t frane_26342_initiator_mode;
   uint8_t frane_26342_bandwidth_mode;
   uint8_t frane_26342_cached_index_size;

   /* V43: resolve the A810/env gate once per command buffer. */
   uint8_t frane_26343_light_dirty_mode;
""",
    "add V43 resolved fastpath gate",
)

anchor = """static uint32_t
frane_26341_build_initiator_base(struct tu_cmd_buffer *cmd)
"""

helper = r'''static inline bool
frane_26343_light_dirty_draw_enabled(struct tu_cmd_buffer *cmd)
{
   /* 0 = unresolved, 1 = disabled/non-A810, 2 = enabled A810. */
   if (unlikely(cmd->state.frane_26343_light_dirty_mode == 0)) {
      static const bool enabled =
         debug_get_bool_option("TU_A810_26343_LIGHT_DIRTY_DRAW", true);

      cmd->state.frane_26343_light_dirty_mode =
         enabled && frane_26341_a810(cmd) ? 2 : 1;
   }

   return cmd->state.frane_26343_light_dirty_mode == 2;
}

static uint32_t
frane_26341_build_initiator_base(struct tu_cmd_buffer *cmd)
'''

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    anchor,
    helper,
    "add cached A810 light-dirty gate",
)

old_tail = """   /* Early exit if there is nothing to emit, saves CPU cycles */
   uint32_t dirty = cmd->state.dirty;
   if (!dynamic_draw_state_dirty && !(dirty & ~TU_CMD_DIRTY_COMPUTE_DESC_SETS))
      return VK_SUCCESS;
"""

new_tail = """   /* V43: the very common VS-params/VB-only case has already done every
    * prerequisite above.  The generic tail would now walk LRZ, tessellation,
    * descriptors, MSAA and FS-parameter tests only to emit these already-built
    * draw states.  Emit the exact same CP_SET_DRAW_STATE payload directly.
    */
   uint32_t dirty = cmd->state.dirty;
   const uint32_t frane_26343_light_mask =
      TU_CMD_DIRTY_VERTEX_BUFFERS | TU_CMD_DIRTY_VS_PARAMS;
   const uint32_t frane_26343_graphics_dirty =
      dirty & ~TU_CMD_DIRTY_COMPUTE_DESC_SETS;

   if (frane_26343_light_dirty_draw_enabled(cmd) &&
       !dynamic_draw_state_dirty &&
       BITSET_IS_EMPTY(cmd->vk.dynamic_graphics_state.dirty) &&
       frane_26343_graphics_dirty &&
       !(frane_26343_graphics_dirty & ~frane_26343_light_mask)) {
      const uint32_t draw_state_count =
         util_bitcount(frane_26343_graphics_dirty);

      tu_cs_emit_pkt7(cs, CP_SET_DRAW_STATE, 3 * draw_state_count);

      if (frane_26343_graphics_dirty & TU_CMD_DIRTY_VERTEX_BUFFERS)
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_VB,
                               cmd->state.vertex_buffers);

      if (frane_26343_graphics_dirty & TU_CMD_DIRTY_VS_PARAMS)
         tu_cs_emit_draw_state(cs, TU_DRAW_STATE_VS_PARAMS,
                               cmd->state.vs_params);

      tu_cs_sanity_check(cs);
      cmd->state.dirty &= TU_CMD_DIRTY_COMPUTE_DESC_SETS;
      return VK_SUCCESS;
   }

   /* Original V42/V39 zero-work early exit. */
   if (!dynamic_draw_state_dirty &&
       !(dirty & ~TU_CMD_DIRTY_COMPUTE_DESC_SETS))
      return VK_SUCCESS;
"""

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    old_tail,
    new_tail,
    "add VS-params/VB-only direct tail",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V42 / Mesa ",
    "Drnas Turnip V43 / Mesa ",
    "V43 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
hdr = (V / "tu_cmd_buffer.h").read_text()
dev = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()

for needle in (
    "TU_A810_26343_LIGHT_DIRTY_DRAW",
    "frane_26343_light_dirty_draw_enabled",
    "frane_26343_light_mask",
    "TU_CMD_DIRTY_VERTEX_BUFFERS | TU_CMD_DIRTY_VS_PARAMS",
    "TU_DRAW_STATE_VB",
    "TU_DRAW_STATE_VS_PARAMS",
):
    assert needle in cmd, needle

assert "frane_26343_light_dirty_mode" in hdr
assert "frane_26342_initiator_dynamic_dirty" in cmd
assert "frane_26342_bandwidth_dynamic_dirty" in cmd
assert 'TU_A810_26341_INITIATOR_CACHE", true' in cmd
assert 'TU_A810_26341_BANDWIDTH_CACHE", true' in cmd
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert "Drnas Turnip V43 / Mesa " in dev

print("Drnas Turnip V43 LIGHT-DIRTY-DRAW applied", flush=True)
