#!/usr/bin/env python3
"""V15-Q A810 bounded GMEM cost experiment, based on image-correct V15-P.

GMEM is physical on-chip tile storage, not an Android/Vulkan RAM allocation.
On A810 the kernel reports the physical size (~576 KiB typical); Mesa
subtracts VPC+color/depth cache reservations to compute usable_gmem_size_gmem
(~448 KiB given V15-P props and one CCU, subject to device report). DO NOT
hardcode 500 KiB, falsify device GMEM geometry, skip attachments or free BOs.

Only the existing A810 bandwidth autotune render-mode decision changes:
- enable guarded GMEM experiment by default, profile=0 restores V15-P;
- check kernel-reported physical bytes and Mesa-computed usable bytes;
- require existing FULL-layout gmem_pixels >0, as computed with ALL actual
  attachments/cpp/alignment/reuse by tu_render_pass_gmem_config;
- make tile COST estimate more conservative by using 15/16 full-layout
  pixels in profile 1, or 31/32 in opt-in profile 2 (not a HW allocator edit);
- allow 18 or 28 estimated tiles and moderately lower bandwidth saving
  entry threshold, to exercise GMEM in real games on small on-chip storage;
- existing Mesa HW mode guards, BO ownership and required load/store stay.

Runtime testing may still reveal hardware faults or missing textures.
Profile 0 + TU_DEBUG=sysmem must be retained as the working rollback.
"""
from pathlib import Path

def edit(path, before, after):
    p=Path("mesa") / path
    s=p.read_text()
    n=s.count(before)
    if n!=1:
        raise SystemExit(f"V15-Q source drift ({path}), occurrences={n}: {before[:120]!r}")
    p.write_text(s.replace(before,after,1))

f="src/freedreno/vulkan/tu_autotune.cc"

# Restore GMEM tests by default; V15-P texture-safe control is still a flag.
edit(f,
    """      /* Safe A810 control: no custom GMEM until SYSMEM textures work. */
      return 0u;""",
    """      /* V15-Q: A810 bounded GMEM experiment; profile 0 restores V15-P
       * for a reliable SYSMEM-first image/texture baseline.
       */
      return 1u;""")

# Physical GMEM metadata must reach the existing per-RP selection function;
# this does not allocate or alter anything on the GPU.
edit(f,
    """                                   uint32_t a830_memory_tier,
                                   bool is_a810)""",
    """                                   uint32_t a830_memory_tier,
                                   bool is_a810,
                                   uint32_t a810_physical_gmem,
                                   uint32_t a810_usable_gmem)""")

# Replace ONLY A810 tile and profitability model, keeping the A830 branch
# exactly unchanged. gmem_pixels is Mesa's computed attachment-safe FULL
# layout, not an invented bytes-per-pixel or a raw frame-size guess.
edit(f,
    """            const uint32_t min_draws =
               is_a810 ? (a810_profile == 2 ? 10u : 12u) : 10u;
            const uint64_t max_tiles =
               is_a810 ? (a810_profile == 2 ? 16u : 8u) : 12u;
            const uint32_t max_pixels =
               is_a810 ? (a810_profile == 2 ? 1600u * 900u
                                             : 1280u * 800u)
                       : 1920u * 1080u;
            const bool measured_candidate =
               a830_memory_tier != 0 &&
               rp_state->drawcall_count >= min_draws &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= max_pixels &&
               approx_tiles <= max_tiles &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;""",
    """            /* Mesa's real tile allocator reserves non-color cache space
             * in fd6_calc_gmem_cache_offsets(), then fits *all* framebuffer
             * attachments into usable_gmem_size_gmem. Never replace that
             * allocator with the user-facing ~500-KiB approximation.
             * This check detects unknown/invalid geometry before opting in.
             */
            const bool a810_layout_safe = !is_a810 ||
               (a810_physical_gmem >= 256u * 1024u &&
                a810_physical_gmem <= 2048u * 1024u &&
                a810_usable_gmem >= 64u * 1024u &&
                a810_usable_gmem <= a810_physical_gmem &&
                pixels_per_tile != 0);
            /* This headroom applies ONLY to our predicted tile count,
             * NOT to actual HW GMEM bytes or attachment offsets.
             * The Mesa layout is always the authority for HW safety.
             */
            const uint64_t effective_a810_tile_pixels =
               pixels_per_tile
                  ? ((pixels_per_tile /
                       (a810_profile == 2 ? 32u : 16u)) *
                     (a810_profile == 2 ? 31u : 15u))
                  : 0;
            const uint64_t a810_tiles =
               is_a810 && effective_a810_tile_pixels
                  ? ((uint64_t)pass_pixel_count +
                     effective_a810_tile_pixels - 1) /
                     effective_a810_tile_pixels
                  : UINT64_MAX;
            const uint64_t estimated_tiles =
               is_a810 ? a810_tiles : approx_tiles;
            const uint32_t min_draws =
               is_a810 ? (a810_profile == 2 ? 8u : 10u) : 10u;
            const uint64_t max_tiles =
               is_a810 ? (a810_profile == 2 ? 28u : 18u) : 12u;
            const uint32_t max_pixels =
               is_a810 ? (a810_profile == 2 ? 1920u * 1080u
                                             : 1600u * 900u)
                       : 1920u * 1080u;
            const bool measured_candidate =
               a830_memory_tier != 0 &&
               a810_layout_safe &&
               rp_state->drawcall_count >= min_draws &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= max_pixels &&
               estimated_tiles <= max_tiles &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;""")

# Qualcomm 842.8 A830 density model should not leak onto A810 when enabled.
edit(f,
    """            const bool q8428_policy =
               use_stats && frane_a830_q8428_policy_enabled();""",
    """            const bool q8428_policy =
               !is_a810 && use_stats && frane_a830_q8428_policy_enabled();""")

edit(f,
    """            const uint32_t tile_penalty =
               is_a810
                  ? (approx_tiles > 2
                        ? (uint32_t) (approx_tiles - 2) *
                             (a810_profile == 2 ? 5u : 12u)
                        : 0u)
                  : base_tile_penalty -
                    (dense_confirmed ? MIN2(base_tile_penalty, 16u) : 0u);""",
    """            /* Small GMEM does not imply GMEM always wins. Charge the
             * *estimated* number of tile reload/store operations, including
             * the headroom above; do not discount actual resolve traffic.
             */
            const uint32_t tile_penalty =
               is_a810
                  ? (estimated_tiles > 4 && estimated_tiles <= max_tiles
                        ? (uint32_t) (estimated_tiles - 4) *
                             (a810_profile == 2 ? 4u : 6u)
                        : 0u)
                  : base_tile_penalty -
                    (dense_confirmed ? MIN2(base_tile_penalty, 16u) : 0u);""")

edit(f,
    """               (is_a810 ? (a810_profile == 2 ? 155u : 220u) : 125u) +
               tile_penalty + low_draw_penalty +""",
    """               (is_a810 ? (a810_profile == 2 ? 125u : 160u) : 125u) +
               tile_penalty + low_draw_penalty +""")

# No new threads, system RAM samples, dynamic allocations, or extra resources.
edit(f,
    """         smart, smart ? frane_a830_gmem_pressure_tier() : 2u,
         frane_a810_gpu(device));""",
    """         smart, smart ? frane_a830_gmem_pressure_tier() : 2u,
         frane_a810_gpu(device),
         device->physical_device->gmem_size,
         device->physical_device->usable_gmem_size_gmem);""")

print("V15-Q: A810 576-KiB-class physical/usable GMEM guard; FULL layout; conservative 18-tile / opt-in 28-tile profiles; V15-P rollback")
