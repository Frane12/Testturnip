#!/usr/bin/env python3
"""Use Mesa's selected tile grid for ordinary full-frame A810 cost estimates."""
from pathlib import Path
R=Path('mesa/src/freedreno/vulkan')
def edit(name,old,new):
 p=R/name;s=p.read_text()
 if s.count(old)!=1: raise SystemExit(f'source drift: {name}: {old[:90]}')
 p.write_text(s.replace(old,new,1))
edit('frane_mesa_2634_a810_gmem_runtime.h',
 '   uint32_t drawcalls = 0;\n',
 '   uint32_t drawcalls = 0;\n   uint64_t selected_tile_count = 0; /* 0: legacy estimate */\n')
edit('frane_mesa_2634_a810_gmem_runtime.h',
 '''   out.estimated_tiles =
      in.pass_pixels / effective_pixels +
      (in.pass_pixels % effective_pixels ? 1ull : 0ull);''',
 '''   out.estimated_tiles = in.selected_tile_count ? in.selected_tile_count :
      in.pass_pixels / effective_pixels +
      (in.pass_pixels % effective_pixels ? 1ull : 0ull);''')
edit('tu_autotune.cc',
 '''         runtime_input.layout.drawcalls = rp_state->drawcall_count;
''',
 '''         runtime_input.layout.drawcalls = rp_state->drawcall_count;

         /* 26.3.21: the allocator has already selected a real 2D tile grid.
          * Only use it for a full-frame, single-layer pass without multiview
          * or FDM. Other cases retain the legacy policy until separately
          * modelled. This changes a performance estimate, not GPU layout.
          */
         static const bool selected_tile_cost =
            debug_get_bool_option("TU_A810_26321_TILE_COST", true);
         const VkRect2D &area = cmd_state->render_areas[0];
         const auto *tiling = cmd_state->tiling;
         if (selected_tile_cost && tiling && tiling->possible &&
             !cmd_state->per_layer_render_area && !pass->has_fdm &&
             pass->num_views == 0 && framebuffer->layers == 1 &&
             area.offset.x == 0 && area.offset.y == 0 &&
             area.extent.width == framebuffer->width &&
             area.extent.height == framebuffer->height &&
             tiling->tile0.width && tiling->tile0.height &&
             tiling->vsc.tile_count.width && tiling->vsc.tile_count.height) {
            runtime_input.layout.pixels_per_tile =
               uint64_t(tiling->tile0.width) * tiling->tile0.height;
            runtime_input.layout.selected_tile_count =
               uint64_t(tiling->vsc.tile_count.width) *
               tiling->vsc.tile_count.height;
         }
''')
edit('tu_device.cc', 'Frane Mesa 26.3.20 A810 GMEM-TURBO EXP / Mesa ',
 'Frane Mesa 26.3.21 A810 TILE-COST EXP / Mesa ')
print('26.3.21 selected tile cost applied')
