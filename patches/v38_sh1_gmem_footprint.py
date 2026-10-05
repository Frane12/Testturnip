#!/usr/bin/env python3
"""A810 V38 SH1 GF1 — allocator-aware GMEM footprint prior.

Runs after V38 GMEM-SEARCH and SH1 shader scheduling. It does not change GMEM
allocation, attachment offsets, tile dimensions, LRZ, sync, or shader order.

GF1 feeds the existing SMART-GMEM prior with:
- exact allocator capacity for the selected GMEM layout (gmem_pixels),
- actual selected tile pixels,
- peak live color/depth-stencil CPP over subpasses,
- peak live GMEM plane count.

MSAA is already represented in attachment cpp. Existing Mesa
sysmem_bandwidth_per_pixel/gmem_bandwidth_per_pixel remains the load/store
traffic signal. Measured PROFILED timing remains authoritative.

A/B:
  TU_FRANE_GMEM_FOOTPRINT=1  default
  TU_FRANE_GMEM_FOOTPRINT=0  exact SH1 policy (all GF1 metadata stays zero)
"""
from pathlib import Path

V = Path("mesa/src/freedreno/vulkan")

def edit(path, old, new, label):
    p = V / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"GF1 source drift {label}: expected 1 anchor, saw {n}: {old[:160]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"GF1 PASS {label}", flush=True)

# Extend the already-existing SMART-GMEM input. Zero is the opt-out sentinel,
# so the old score is byte-for-byte unchanged when GF1 is disabled.
edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   uint32_t gmem_bandwidth_per_pixel = 0;
};""",
    """   uint32_t gmem_bandwidth_per_pixel = 0;

   /* V38 SH1 GF1: allocator-aware metadata. Zero means unavailable/disabled. */
   uint64_t allocator_capacity_pixels = 0;
   uint64_t selected_tile_pixels = 0;
   uint32_t peak_live_cpp = 0;
   uint32_t peak_color_cpp = 0;
   uint32_t peak_ds_cpp = 0;
   uint32_t peak_live_planes = 0;
};""",
    "extend SMART-GMEM input with exact footprint metadata",
)

anchor = """static inline frane_26318_smart_gmem_eval
frane_26318_eval_smart_gmem(const frane_26318_smart_gmem_input &in)
{"""

helper = r"""struct frane_v38_gf1_eval {
   bool valid = false;
   uint8_t score_bonus = 0; /* bounded 0..22 */
   uint8_t capacity_fill_pct = 0;
   uint8_t raw_footprint_pct = 0;
};

static inline bool
frane_v38_gf1_ratio_ge(uint64_t lhs, uint64_t rhs,
                       uint32_t num, uint32_t den)
{
   if (!rhs || !den || num > den)
      return false;

   const uint64_t q = rhs / den;
   const uint64_t r = rhs % den;
   const uint64_t threshold =
      q * num + (r * num + den - 1u) / den;
   return lhs >= threshold;
}

static inline uint8_t
frane_v38_gf1_pct(uint64_t lhs, uint64_t rhs)
{
   if (!rhs)
      return 0;
   if (lhs >= rhs)
      return 100;

   const uint64_t q = lhs / rhs;
   const uint64_t r = lhs % rhs;
   (void)q; /* q is zero in the lhs < rhs path. */
   return uint8_t((r * 100u) / rhs);
}

static inline frane_v38_gf1_eval
frane_v38_gf1_eval_footprint(const frane_26318_smart_gmem_input &in)
{
   frane_v38_gf1_eval out {};

   const uint64_t capacity = in.allocator_capacity_pixels;
   const uint64_t tile = in.selected_tile_pixels;
   const uint64_t cpp = in.peak_live_cpp;
   const uint64_t usable = in.layout.usable_gmem;

   if (!capacity || !tile || tile > capacity || !cpp || !usable)
      return out;

   if (cpp > UINT64_MAX / tile)
      return out;

   const uint64_t raw_bytes = tile * cpp;

   /* The exact allocator capacity is the authority. If this simple
    * per-subpass CPP model disagrees with the allocator's usable-GMEM bound,
    * treat the model as unknown rather than penalizing a legal layout.
    */
   if (raw_bytes > usable)
      return out;

   out.valid = true;
   out.capacity_fill_pct = frane_v38_gf1_pct(tile, capacity);
   out.raw_footprint_pct = frane_v38_gf1_pct(raw_bytes, usable);

   unsigned bonus = 0;

   /* How closely the selected tile uses the exact V38 allocator capacity. */
   if (frane_v38_gf1_ratio_ge(tile, capacity, 7, 8))
      bonus += 12;
   else if (frane_v38_gf1_ratio_ge(tile, capacity, 3, 4))
      bonus += 9;
   else if (frane_v38_gf1_ratio_ge(tile, capacity, 5, 8))
      bonus += 6;
   else if (frane_v38_gf1_ratio_ge(tile, capacity, 1, 2))
      bonus += 3;

   /* Approximate live attachment bytes inside that tile. This is deliberately
    * secondary to exact allocator capacity and existing Mesa BW metadata.
    */
   if (frane_v38_gf1_ratio_ge(raw_bytes, usable, 3, 4))
      bonus += 8;
   else if (frane_v38_gf1_ratio_ge(raw_bytes, usable, 1, 2))
      bonus += 5;
   else if (frane_v38_gf1_ratio_ge(raw_bytes, usable, 1, 3))
      bonus += 3;

   /* Multiple simultaneously live planes make on-chip reuse more interesting.
    * Keep this tiny: bandwidth + measured timing still dominate.
    */
   if (in.peak_live_planes >= 4)
      bonus += 2;
   else if (in.peak_live_planes >= 2)
      bonus += 1;

   out.score_bonus = uint8_t(MIN2(bonus, 22u));
   return out;
}

static inline frane_26318_smart_gmem_eval
frane_26318_eval_smart_gmem(const frane_26318_smart_gmem_input &in)
{"""

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    anchor,
    helper,
    "add bounded footprint evaluator",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   out.structure_score = uint8_t(std::clamp(score, 0, 100));
   return out;
}""",
    """   const auto gf1 = frane_v38_gf1_eval_footprint(in);
   if (gf1.valid)
      score += gf1.score_bonus;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));
   return out;
}""",
    "blend footprint prior into existing bounded structural score",
)

# A810-only runtime gate. It only controls metadata population.
edit(
    "tu_autotune.cc",
    """static bool
frane_a810_gmem_safety_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_gmem_footprint_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_GMEM_FOOTPRINT", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_gmem_safety_enabled(const struct tu_device *device)
{""",
    "add default-on A810 GF1 gate",
)

# Populate metadata immediately before the existing Mesa BW metadata.
edit(
    "tu_autotune.cc",
    """         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;""",
    r"""         if (frane_a810_gmem_footprint_enabled(device) &&
             cmd_state->tiling && cmd_state->tiling->possible &&
             cmd_state->tiling->tile0.width &&
             cmd_state->tiling->tile0.height &&
             pass->subpass_count > 0 &&
             cmd_state->gmem_layout < TU_GMEM_LAYOUT_COUNT) {
            const uint64_t tile_pixels =
               uint64_t(cmd_state->tiling->tile0.width) *
               cmd_state->tiling->tile0.height;
            const uint64_t capacity_pixels =
               pass->gmem_pixels[cmd_state->gmem_layout];

            uint64_t peak_live_cpp = 0;
            uint64_t peak_color_cpp = 0;
            uint64_t peak_ds_cpp = 0;
            uint32_t peak_planes = 0;

            for (uint32_t sp = 0; sp < pass->subpass_count; sp++) {
               uint64_t color_cpp = 0;
               uint64_t ds_cpp = 0;
               uint32_t planes = 0;

               for (uint32_t i = 0; i < pass->attachment_count; i++) {
                  const struct tu_render_pass_attachment &att =
                     pass->attachments[i];

                  if (!att.gmem ||
                      sp < att.first_subpass_idx ||
                      sp > att.last_subpass_idx)
                     continue;

                  if (vk_format_is_depth_or_stencil(att.format)) {
                     ds_cpp += att.cpp;
                     planes++;

                     /* Turnip stores D32S8 stencil in a separate GMEM plane.
                      * att.cpp already contains depth bytes * samples; stencil
                      * contributes one byte per sample.
                      */
                     if (att.format == VK_FORMAT_D32_SFLOAT_S8_UINT) {
                        ds_cpp += uint32_t(att.samples);
                        planes++;
                     }
                  } else {
                     color_cpp += att.cpp;
                     planes++;
                  }
               }

               const uint64_t live_cpp = color_cpp + ds_cpp;
               if (live_cpp > peak_live_cpp) {
                  peak_live_cpp = live_cpp;
                  peak_color_cpp = color_cpp;
                  peak_ds_cpp = ds_cpp;
                  peak_planes = planes;
               }
            }

            if (tile_pixels && capacity_pixels &&
                tile_pixels <= capacity_pixels &&
                peak_live_cpp <= UINT32_MAX &&
                peak_color_cpp <= UINT32_MAX &&
                peak_ds_cpp <= UINT32_MAX) {
               runtime_input.allocator_capacity_pixels = capacity_pixels;
               runtime_input.selected_tile_pixels = tile_pixels;
               runtime_input.peak_live_cpp = uint32_t(peak_live_cpp);
               runtime_input.peak_color_cpp = uint32_t(peak_color_cpp);
               runtime_input.peak_ds_cpp = uint32_t(peak_ds_cpp);
               runtime_input.peak_live_planes = peak_planes;
            }
         }

         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;""",
    "feed selected-layout capacity and peak live attachments to SMART-GMEM",
)

edit(
    "tu_device.cc",
    "Turnip-Drnas A810 V38 SH1 / Mesa ",
    "Turnip-Drnas A810 V38 SH1 GF1 / Mesa ",
    "GF1 driver identity",
)

h = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()

for needle in (
    "frane_v38_gf1_eval_footprint",
    "allocator_capacity_pixels",
    "selected_tile_pixels",
    "peak_live_cpp",
    "score_bonus",
):
    assert needle in h, needle

for needle in (
    'TU_FRANE_GMEM_FOOTPRINT", true',
    "pass->gmem_pixels[cmd_state->gmem_layout]",
    "att.first_subpass_idx",
    "att.last_subpass_idx",
    "VK_FORMAT_D32_SFLOAT_S8_UINT",
    "runtime_input.peak_ds_cpp",
):
    assert needle in a, needle

assert "Turnip-Drnas A810 V38 SH1 GF1 / Mesa " in d
assert 'TU_FRANE_SHADER_MODE", 1' in (Path("mesa/src/freedreno/ir3/ir3_compiler.c")).read_text()

print("A810 V38 SH1 GF1 allocator-aware GMEM footprint prior applied", flush=True)
