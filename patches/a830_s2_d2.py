#!/usr/bin/env python3
"""A830 S2-D2 thin layer over the validated S1 Smart patch.

Goals:
  1) feed exact selected-layout/tile/live-attachment footprint into the existing
     SMART-GMEM structural prior without changing allocation or safety gates;
  2) keep the existing adaptive IR3 scheduler, but use its register-pressure
     tie-break only once live pressure crosses an A830-tunable threshold;
  3) include the runtime scheduler knobs in the IR3 disk-cache namespace.

A/B controls:
  TU_FRANE_A830_FOOTPRINT=1  default
  TU_FRANE_A830_FOOTPRINT=0  exact S1 Smart GMEM policy
  TU_FRANE_A830_SHADER_PRESSURE=42  default, clamped 20..80

This script must run after patches/a830-smart2-complete.patch.
"""

from pathlib import Path
import hashlib
import shutil

ROOT = Path("mesa/src/freedreno")
V = ROOT / "vulkan"
I = ROOT / "ir3"

before = {
    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ROOT.rglob("*") if p.is_file()
}

def edit(path: Path, old: str, new: str, label: str) -> None:
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"S2-D2 source drift {label}: expected one anchor, saw {n}: {old[:180]!r}"
        )
    path.write_text(s.replace(old, new, 1))
    print(f"S2-D2 PASS {label}", flush=True)

# Pure policy headers are kept in the repo and copied into the Mesa tree.
shutil.copyfile("patches/frane_a830_s2d2_gmem.h",
                V / "frane_a830_s2d2_gmem.h")
shutil.copyfile("patches/frane_a830_s2d2_sched.h",
                I / "frane_a830_s2d2_sched.h")

# ---------------------------------------------------------------------------
# GMEM: augment the existing SMART-GMEM input, no second selector.
# ---------------------------------------------------------------------------
edit(
    V / "frane_mesa_26318_a810_smart_gmem.h",
    '#include "frane_mesa_2634_a810_gmem_runtime.h"',
    '#include "frane_mesa_2634_a810_gmem_runtime.h"\n'
    '#include "frane_a830_s2d2_gmem.h"',
    "include S2-D2 GMEM helper",
)

edit(
    V / "frane_mesa_26318_a810_smart_gmem.h",
    """   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
};""",
    """   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;

   /* A830 S2-D2: exact allocator/tile metadata. Zero means unavailable. */
   uint64_t allocator_capacity_pixels = 0;
   uint64_t selected_tile_pixels = 0;
   uint32_t peak_live_cpp = 0;
   uint32_t peak_live_planes = 0;
};""",
    "extend SMART-GMEM input",
)

edit(
    V / "frane_mesa_26318_a810_smart_gmem.h",
    """   out.structure_score = uint8_t(std::clamp(score, 0, 100));
   return out;
}""",
    """   const auto s2d2 = frane_a830_s2d2_eval_footprint(
      in.allocator_capacity_pixels,
      in.selected_tile_pixels,
      in.peak_live_cpp,
      in.layout.usable_gmem,
      in.peak_live_planes);
   if (s2d2.valid)
      score += s2d2.score_bonus;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));
   return out;
}""",
    "blend bounded A830 footprint prior",
)

edit(
    V / "tu_autotune.cc",
    """static bool
frane_26320_a830_smart_gmem_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A830_26320_SMART_GMEM", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
    """static bool
frane_26320_a830_smart_gmem_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A830_26320_SMART_GMEM", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_s2d2_footprint_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_FOOTPRINT", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
    "add A830 footprint runtime gate",
)

edit(
    V / "tu_autotune.cc",
    """         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;""",
    """         if (frane_a830_s2d2_footprint_enabled(device) &&
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
            uint32_t peak_live_planes = 0;

            for (uint32_t sp = 0; sp < pass->subpass_count; sp++) {
               uint64_t live_cpp = 0;
               uint32_t live_planes = 0;

               for (uint32_t i = 0; i < pass->attachment_count; i++) {
                  const struct tu_render_pass_attachment &att =
                     pass->attachments[i];

                  if (!att.gmem ||
                      sp < att.first_subpass_idx ||
                      sp > att.last_subpass_idx)
                     continue;

                  live_cpp += att.cpp;
                  live_planes++;

                  /* D32S8 has a separate stencil GMEM plane. The guarded
                   * A830 path currently admits sample-count 1 only, but use
                   * att.samples here so the metadata remains structurally
                   * correct if that scope changes later.
                   */
                  if (att.format == VK_FORMAT_D32_SFLOAT_S8_UINT) {
                     live_cpp += uint32_t(att.samples);
                     live_planes++;
                  }
               }

               if (live_cpp > peak_live_cpp) {
                  peak_live_cpp = live_cpp;
                  peak_live_planes = live_planes;
               }
            }

            if (tile_pixels && capacity_pixels &&
                tile_pixels <= capacity_pixels &&
                peak_live_cpp <= UINT32_MAX) {
               runtime_input.allocator_capacity_pixels = capacity_pixels;
               runtime_input.selected_tile_pixels = tile_pixels;
               runtime_input.peak_live_cpp = uint32_t(peak_live_cpp);
               runtime_input.peak_live_planes = peak_live_planes;
            }
         }

         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;""",
    "feed allocator-aware A830 footprint metadata",
)

# ---------------------------------------------------------------------------
# IR3: low pressure keeps latency-oriented tie-break; high pressure uses the
# existing live-range-aware tie-break. The existing dynamic sy window remains.
# ---------------------------------------------------------------------------
edit(
    I / "ir3_compiler.c",
    '#include "ir3_compiler.h"',
    '#include "ir3_compiler.h"\n#include "frane_a830_s2d2_sched.h"',
    "include S2-D2 scheduler policy in compiler",
)

edit(
    I / "ir3_sched.c",
    '#include "ir3_compiler.h"',
    '#include "ir3_compiler.h"\n#include "frane_a830_s2d2_sched.h"',
    "include S2-D2 scheduler policy in scheduler",
)

edit(
    I / "ir3_compiler.h",
    """   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;""",
    """   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;

   /* S2-D2: only let live-range tie-break dominate above this pressure. */
   uint8_t frane_a830_s2d2_pressure_threshold;""",
    "store A830 pressure threshold",
)

edit(
    I / "ir3_compiler.c",
    """      compiler->frane_26317_tex_window_max =
         MIN2(16u, MAX2(8u, frane_tex_window));
   }""",
    """      compiler->frane_26317_tex_window_max =
         MIN2(16u, MAX2(8u, frane_tex_window));

      compiler->frane_a830_s2d2_pressure_threshold =
         frane_a830_s2d2_pressure_threshold(
            debug_get_num_option("TU_FRANE_A830_SHADER_PRESSURE", 42));
   }""",
    "initialize A830 pressure threshold",
)

p = I / "ir3_sched.c"
s = p.read_text()

start = s.index("\nchoose_instr_dec(struct ir3_sched_ctx *ctx")
stop = s.index("enum choose_instr_inc_rank", start)
body = s[start:stop]

anchor = """   enum choose_instr_dec_rank chosen_rank = DEC_NEUTRAL;
   int chosen_live = 0;"""
if body.count(anchor) != 1:
    raise SystemExit("S2-D2 source drift choose_instr_dec declaration")
body = body.replace(
    anchor,
    anchor + """
   const bool pressure_priority = frane_a830_s2d2_pressure_priority(
      ctx->compiler->frane_26317_adaptive_sched,
      frane_26317_pressure_pct(ctx),
      ctx->compiler->frane_a830_s2d2_pressure_threshold);""",
    1,
)
if body.count("ctx->compiler->frane_26317_adaptive_sched &&\n             live < chosen_live") != 1:
    raise SystemExit("S2-D2 source drift choose_instr_dec priority")
body = body.replace(
    "ctx->compiler->frane_26317_adaptive_sched &&\n             live < chosen_live",
    "pressure_priority &&\n             live < chosen_live",
    1,
)
if body.count("(!ctx->compiler->frane_26317_adaptive_sched ||\n                     live == chosen_live)") != 1:
    raise SystemExit("S2-D2 source drift choose_instr_dec fallback")
body = body.replace(
    "(!ctx->compiler->frane_26317_adaptive_sched ||\n                     live == chosen_live)",
    "(!pressure_priority ||\n                     live == chosen_live)",
    1,
)
s = s[:start] + body + s[stop:]

start = s.index("\nchoose_instr_inc(struct ir3_sched_ctx *ctx")
stop = s.index("static struct ir3_sched_node *\nchoose_instr_prio", start)
body = s[start:stop]

anchor = """   unsigned chosen_distance = 0;
   int chosen_live_growth = 0;"""
if body.count(anchor) != 1:
    raise SystemExit("S2-D2 source drift choose_instr_inc declaration")
body = body.replace(
    anchor,
    anchor + """
   const bool pressure_priority = frane_a830_s2d2_pressure_priority(
      ctx->compiler->frane_26317_adaptive_sched,
      frane_26317_pressure_pct(ctx),
      ctx->compiler->frane_a830_s2d2_pressure_threshold);""",
    1,
)
if body.count("int live_growth = ctx->compiler->frane_26317_adaptive_sched ?\n         live_effect(n->instr) : 0;") != 1:
    raise SystemExit("S2-D2 source drift choose_instr_inc live growth")
body = body.replace(
    "int live_growth = ctx->compiler->frane_26317_adaptive_sched ?\n         live_effect(n->instr) : 0;",
    "int live_growth = pressure_priority ? live_effect(n->instr) : 0;",
    1,
)
if body.count("ctx->compiler->frane_26317_adaptive_sched &&\n             live_growth < chosen_live_growth") != 1:
    raise SystemExit("S2-D2 source drift choose_instr_inc priority")
body = body.replace(
    "ctx->compiler->frane_26317_adaptive_sched &&\n             live_growth < chosen_live_growth",
    "pressure_priority &&\n             live_growth < chosen_live_growth",
    1,
)
if body.count("(!ctx->compiler->frane_26317_adaptive_sched ||\n                     live_growth == chosen_live_growth)") != 1:
    raise SystemExit("S2-D2 source drift choose_instr_inc fallback")
body = body.replace(
    "(!ctx->compiler->frane_26317_adaptive_sched ||\n                     live_growth == chosen_live_growth)",
    "(!pressure_priority ||\n                     live_growth == chosen_live_growth)",
    1,
)
s = s[:start] + body + s[stop:]
p.write_text(s)
print("S2-D2 PASS pressure-gated scheduler tie-break", flush=True)

# Runtime compile options change generated code. Keep shader disk cache
# separated when these knobs differ.
edit(
    I / "ir3_disk_cache.c",
    """   _mesa_blake3_update(&ctx, &compiler->options.uche_trap_base,
                     sizeof(compiler->options.uche_trap_base));
   _mesa_blake3_final(&ctx, blake3);""",
    """   _mesa_blake3_update(&ctx, &compiler->options.uche_trap_base,
                     sizeof(compiler->options.uche_trap_base));
   _mesa_blake3_update(&ctx, &compiler->frane_26317_adaptive_sched,
                     sizeof(compiler->frane_26317_adaptive_sched));
   _mesa_blake3_update(&ctx, &compiler->frane_26317_tex_window_max,
                     sizeof(compiler->frane_26317_tex_window_max));
   _mesa_blake3_update(&ctx, &compiler->frane_a830_s2d2_pressure_threshold,
                     sizeof(compiler->frane_a830_s2d2_pressure_threshold));
   _mesa_blake3_final(&ctx, blake3);""",
    "key IR3 disk cache by scheduler knobs",
)

edit(
    V / "tu_device.cc",
    "Drnas Turnip A830 S1 Smart Performance 2 / Mesa ",
    "Turnip-Drnas A830 S2-D2 / Mesa ",
    "S2-D2 driver identity",
)

# Integration assertions.
smart = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
auto = (V / "tu_autotune.cc").read_text()
sched = (I / "ir3_sched.c").read_text()
compiler = (I / "ir3_compiler.c").read_text()
cache = (I / "ir3_disk_cache.c").read_text()
device = (V / "tu_device.cc").read_text()

for needle in (
    "frane_a830_s2d2_eval_footprint",
    "allocator_capacity_pixels",
    "selected_tile_pixels",
    "peak_live_cpp",
    "peak_live_planes",
):
    assert needle in smart, needle

for needle in (
    'TU_FRANE_A830_FOOTPRINT", true',
    "pass->gmem_pixels[cmd_state->gmem_layout]",
    "att.first_subpass_idx",
    "att.last_subpass_idx",
    "VK_FORMAT_D32_SFLOAT_S8_UINT",
):
    assert needle in auto, needle

for needle in (
    "frane_a830_s2d2_pressure_priority",
    "pressure_priority &&",
    "!pressure_priority ||",
):
    assert needle in sched, needle

assert 'TU_FRANE_A830_SHADER_PRESSURE", 42' in compiler
assert "frane_a830_s2d2_pressure_threshold" in cache
assert "Turnip-Drnas A830 S2-D2 / Mesa " in device

after = {
    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ROOT.rglob("*") if p.is_file()
}
changed = {k for k in before.keys() | after.keys()
           if before.get(k) != after.get(k)}
expected = {
    "ir3/frane_a830_s2d2_sched.h",
    "ir3/ir3_compiler.c",
    "ir3/ir3_compiler.h",
    "ir3/ir3_disk_cache.c",
    "ir3/ir3_sched.c",
    "vulkan/frane_a830_s2d2_gmem.h",
    "vulkan/frane_mesa_26318_a810_smart_gmem.h",
    "vulkan/tu_autotune.cc",
    "vulkan/tu_device.cc",
}
if changed != expected:
    raise SystemExit(f"S2-D2 unexpected source scope: {sorted(changed ^ expected)}")

print("A830 S2-D2 layer applied; source scope verified", flush=True)
