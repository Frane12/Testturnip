#!/usr/bin/env python3
"""Turnip A810 V41 CLEAN-DRAW-FASTPATH.

Layered strictly on the V39 golden GMEM-PRESSURE baseline.

This experiment targets code that executes on essentially every ordinary draw
rather than another GMEM allocation heuristic.  It adds two independent,
default-on A810 CPU-side caches:

  1) draw-initiator base cache
     CP_DRAW_INDX_OFFSET's topology / index-size / GS / tessellation bits are
     invariant across clean draws.  Rebuild them only when graphics/dynamic
     state changed, then OR only SOURCE_SELECT at each draw.

  2) per-draw autotune bandwidth cache
     The autotuner currently re-adds color + optional depth/stencil bandwidth
     with several branches on every draw.  Cache the exact derived value and
     rebuild it whenever any graphics or dynamic state changed.

The invalidation rule is intentionally broader than necessary: ANY graphics
or dynamic-state dirtiness refreshes both caches.  This keeps the experiment
conservative while still removing work from the common clean-draw path.

A/B:
  TU_A810_26341_INITIATOR_CACHE=0
  TU_A810_26341_BANDWIDTH_CACHE=0
Disabling both restores V39 logic for these two paths.
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
            f"V41 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V41 PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# Cache storage is part of tu_cmd_state so command-buffer begin's existing
# memset naturally starts both caches invalid.  No new lifetime management.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_cmd_buffer.h",
    """   struct tu_vs_params last_vs_params;
   bool last_draw_indexed;

   /* Set by tu_sw_multiview_draw() while it replays a draw for a single view
""",
    """   struct tu_vs_params last_vs_params;
   bool last_draw_indexed;

   /* V41 A810 clean-draw CPU caches.  Both are refreshed after any graphics
    * or dynamic-state change and therefore are only consumed on state that
    * has already passed through the ordinary Turnip update path.
    */
   uint32_t frane_26341_initiator_base;
   uint32_t frane_26341_draw_bandwidth;
   bool frane_26341_initiator_valid;
   bool frane_26341_bandwidth_valid;

   /* Set by tu_sw_multiview_draw() while it replays a draw for a single view
""",
    "add command-buffer-local clean-draw caches",
)

# ---------------------------------------------------------------------------
# Helpers are placed immediately before tu6_draw_common.  Keep A810 gating
# explicit and keep the two experiments independently switchable.
# ---------------------------------------------------------------------------
anchor = """template <chip CHIP>
static VkResult
tu6_draw_common(struct tu_cmd_buffer *cmd,
"""

helpers = r'''static bool
frane_26341_a810(const struct tu_cmd_buffer *cmd)
{
   if (!cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == UINT64_C(0x44010000) ||
          chip == UINT64_C(0xffff44010000);
}

static bool
frane_26341_initiator_cache_enabled(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26341_INITIATOR_CACHE", true);
   return enabled && frane_26341_a810(cmd);
}

static bool
frane_26341_bandwidth_cache_enabled(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26341_BANDWIDTH_CACHE", true);
   return enabled && frane_26341_a810(cmd);
}

static uint32_t
frane_26341_build_initiator_base(struct tu_cmd_buffer *cmd)
{
   enum pc_di_primtype primtype =
      tu6_primtype((VkPrimitiveTopology)
         cmd->vk.dynamic_graphics_state.ia.primitive_topology);

   if (primtype == DI_PT_PATCHES0)
      primtype = (enum pc_di_primtype)(
         primtype + cmd->vk.dynamic_graphics_state.ts.patch_control_points);

   uint32_t initiator =
      CP_DRAW_INDX_OFFSET_0_PRIM_TYPE(primtype) |
      CP_DRAW_INDX_OFFSET_0_INDEX_SIZE(
         (enum a4xx_index_size) cmd->state.index_size) |
      CP_DRAW_INDX_OFFSET_0_VIS_CULL(USE_VISIBILITY);

   if (cmd->state.shaders[MESA_SHADER_GEOMETRY]->variant)
      initiator |= CP_DRAW_INDX_OFFSET_0_GS_ENABLE;

   const struct tu_shader *tes =
      cmd->state.shaders[MESA_SHADER_TESS_EVAL];
   if (tes->variant) {
      switch (tes->variant->key.tessellation) {
      case IR3_TESS_TRIANGLES:
         initiator |= CP_DRAW_INDX_OFFSET_0_PATCH_TYPE(TESS_TRIANGLES) |
                      CP_DRAW_INDX_OFFSET_0_TESS_ENABLE;
         break;
      case IR3_TESS_ISOLINES:
         initiator |= CP_DRAW_INDX_OFFSET_0_PATCH_TYPE(TESS_ISOLINES) |
                      CP_DRAW_INDX_OFFSET_0_TESS_ENABLE;
         break;
      case IR3_TESS_QUADS:
         initiator |= CP_DRAW_INDX_OFFSET_0_PATCH_TYPE(TESS_QUADS) |
                      CP_DRAW_INDX_OFFSET_0_TESS_ENABLE;
         break;
      }
   }

   return initiator;
}

static uint32_t
frane_26341_calc_draw_bandwidth(const struct tu_cmd_buffer *cmd)
{
   uint32_t value = cmd->state.bandwidth.color_bandwidth_per_sample;

   const uint32_t depth = cmd->state.bandwidth.depth_cpp_per_sample;
   if (cmd->vk.dynamic_graphics_state.ds.depth.write_enable)
      value += depth;
   if (cmd->vk.dynamic_graphics_state.ds.depth.test_enable)
      value += depth;

   if (cmd->vk.dynamic_graphics_state.ds.stencil.test_enable)
      value += cmd->state.bandwidth.stencil_cpp_per_sample * 2;

   return value;
}

template <chip CHIP>
static VkResult
tu6_draw_common(struct tu_cmd_buffer *cmd,
'''

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    anchor,
    helpers,
    "add A810 clean-draw cache helpers",
)

# ---------------------------------------------------------------------------
# Snapshot whether ordinary state work was needed BEFORE tu_emit_draw_state.
# If anything changed, refresh the pure derived caches afterwards.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   /* Emit state first, because it's needed for bandwidth calculations */
   uint32_t dynamic_draw_state_dirty = 0;
   if (!BITSET_IS_EMPTY(cmd->vk.dynamic_graphics_state.dirty) ||
       (cmd->state.dirty & ~TU_CMD_DIRTY_COMPUTE_DESC_SETS)) {
      dynamic_draw_state_dirty = tu_emit_draw_state<CHIP>(cmd);
   }
""",
    """   /* Emit state first, because it's needed for bandwidth calculations.
    * V41 snapshots whether any graphics/dynamic state was dirty before the
    * ordinary update.  A dirty snapshot conservatively invalidates both pure
    * clean-draw caches; no attempt is made to classify only relevant bits.
    */
   const bool frane_26341_graphics_dirty =
      !BITSET_IS_EMPTY(cmd->vk.dynamic_graphics_state.dirty) ||
      (cmd->state.dirty & ~TU_CMD_DIRTY_COMPUTE_DESC_SETS);

   uint32_t dynamic_draw_state_dirty = 0;
   if (frane_26341_graphics_dirty) {
      dynamic_draw_state_dirty = tu_emit_draw_state<CHIP>(cmd);
   }
""",
    "snapshot clean-vs-dirty draw state",
)

old_bw = """   /* Fill draw stats for autotuner */
   rp->drawcall_count++;

   rp->drawcall_bandwidth_per_sample_sum +=
      cmd->state.bandwidth.color_bandwidth_per_sample;

   /* add depth memory bandwidth cost */
   const uint32_t depth_bandwidth = cmd->state.bandwidth.depth_cpp_per_sample;
   if (cmd->vk.dynamic_graphics_state.ds.depth.write_enable)
      rp->drawcall_bandwidth_per_sample_sum += depth_bandwidth;
   if (cmd->vk.dynamic_graphics_state.ds.depth.test_enable)
      rp->drawcall_bandwidth_per_sample_sum += depth_bandwidth;

   /* add stencil memory bandwidth cost */
   const uint32_t stencil_bandwidth =
      cmd->state.bandwidth.stencil_cpp_per_sample;
   if (cmd->vk.dynamic_graphics_state.ds.stencil.test_enable)
      rp->drawcall_bandwidth_per_sample_sum += stencil_bandwidth * 2;
"""

new_bw = """   /* Refresh derived clean-draw caches only after Turnip has consumed any
    * pending state changes.  First use is also a refresh because command
    * buffer begin zero-initializes the validity bits.
    */
   if (frane_26341_initiator_cache_enabled(cmd) &&
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

   /* Fill draw stats for autotuner.  V39 semantics are retained exactly when
    * the cache is disabled.  On the clean A810 path this becomes one cached
    * load + add instead of repeated depth/stencil tests every draw.
    */
   rp->drawcall_count++;

   if (frane_26341_bandwidth_cache_enabled(cmd) &&
       cmd->state.frane_26341_bandwidth_valid) {
      rp->drawcall_bandwidth_per_sample_sum +=
         cmd->state.frane_26341_draw_bandwidth;
   } else {
      rp->drawcall_bandwidth_per_sample_sum +=
         cmd->state.bandwidth.color_bandwidth_per_sample;

      const uint32_t depth_bandwidth =
         cmd->state.bandwidth.depth_cpp_per_sample;
      if (cmd->vk.dynamic_graphics_state.ds.depth.write_enable)
         rp->drawcall_bandwidth_per_sample_sum += depth_bandwidth;
      if (cmd->vk.dynamic_graphics_state.ds.depth.test_enable)
         rp->drawcall_bandwidth_per_sample_sum += depth_bandwidth;

      const uint32_t stencil_bandwidth =
         cmd->state.bandwidth.stencil_cpp_per_sample;
      if (cmd->vk.dynamic_graphics_state.ds.stencil.test_enable)
         rp->drawcall_bandwidth_per_sample_sum += stencil_bandwidth * 2;
   }
"""

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    old_bw,
    new_bw,
    "cache exact per-draw autotune bandwidth on clean draws",
)

# ---------------------------------------------------------------------------
# Keep the original initiator logic as the exact fallback.  The fast path
# merely reuses the previously-derived invariant base and adds SOURCE_SELECT.
# This also covers AUTO_XFB without a separate cache entry.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """static uint32_t
tu_draw_initiator(struct tu_cmd_buffer *cmd, enum pc_di_src_sel src_sel)
{
   enum pc_di_primtype primtype =
""",
    """static uint32_t
tu_draw_initiator(struct tu_cmd_buffer *cmd, enum pc_di_src_sel src_sel)
{
   if (frane_26341_initiator_cache_enabled(cmd) &&
       cmd->state.frane_26341_initiator_valid) {
      return cmd->state.frane_26341_initiator_base |
             CP_DRAW_INDX_OFFSET_0_SOURCE_SELECT(src_sel);
   }

   enum pc_di_primtype primtype =
""",
    "reuse cached invariant draw-initiator base",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Turnip A810 V39 / Mesa ",
    "Turnip A810 V41 / Mesa ",
    "short V41 identity",
)

# ---------------------------------------------------------------------------
# Surgical guards: V41 must not disturb the golden rendering/GMEM stack.
# ---------------------------------------------------------------------------
cmd = (V / "tu_cmd_buffer.cc").read_text()
hdr = (V / "tu_cmd_buffer.h").read_text()
autotune = (V / "tu_autotune.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
dev = (V / "tu_device.cc").read_text()

for needle in (
    "TU_A810_26341_INITIATOR_CACHE",
    "TU_A810_26341_BANDWIDTH_CACHE",
    "frane_26341_build_initiator_base",
    "frane_26341_calc_draw_bandwidth",
    "frane_26341_graphics_dirty",
):
    assert needle in cmd, needle

for needle in (
    "frane_26341_initiator_base",
    "frane_26341_draw_bandwidth",
    "frane_26341_initiator_valid",
    "frane_26341_bandwidth_valid",
):
    assert needle in hdr, needle

# Correctness work retained.
assert "frane_26313_same_lrz_fs_signature" not in cmd
assert "cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;" in cmd
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert "V28-CLEAN: no driver present-mode override" in (
    V / "tu_wsi.cc").read_text()
assert "Turnip A810 V41 / Mesa " in dev

# The fallback V39 initiator expression must still exist.
assert "CP_DRAW_INDX_OFFSET_0_SOURCE_SELECT(src_sel)" in cmd
assert "CP_DRAW_INDX_OFFSET_0_GS_ENABLE" in cmd
assert "IR3_TESS_QUADS" in cmd

print("Turnip A810 V41 CLEAN-DRAW-FASTPATH applied", flush=True)
