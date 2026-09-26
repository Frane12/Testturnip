#!/usr/bin/env python3
"""Frane Mesa 26.3.4 A810 GMEM-RUNTIME EXP.

Layered strictly on green 26.3.3 PROFILE-TURBO. Keep PROFILED and the per-game
cache as the primary learner. This runtime only promotes already-measured,
strong GMEM winners and periodically probes SYSMEM so it can self-disarm.
Unknown/unsafe-looking geometry leaves the 26.3.3 decision untouched.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.4 GMEM-RUNTIME source drift: {label}: expected 1 anchor, saw {n}: {old[:150]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.4 GMEM-RUNTIME PASS {label}", flush=True)

shutil.copyfile("patches/frane_mesa_2634_a810_gmem_runtime.h",
                V / "frane_mesa_2634_a810_gmem_runtime.h")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''#include "frane_mesa_2633_a810_profile_turbo.h"''',
'''#include "frane_mesa_2633_a810_profile_turbo.h"
#include "frane_mesa_2634_a810_gmem_runtime.h"''',
"include pure GMEM runtime policy")

# Runtime defaults ON only in this experimental A810 build. The normal user
# setup still needs only TU_FRANE_PROFILE_ID=<game>; this is an opt-out.
edit("src/freedreno/vulkan/tu_autotune.cc",
'''static bool
frane_a810_lean_profiled()
{''',
'''static bool
frane_a810_gmem_runtime_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_GMEM_RUNTIME", true);
   if (!enabled || !device || !device->physical_device)
      return false;
   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_lean_profiled()
{''',
"default-on A810 runtime with opt-out")

# State is updated only from the submit-side measurement processing path.
# Recording threads consume only the packed relaxed-atomic snapshot.
edit("src/freedreno/vulkan/tu_autotune.cc",
'''   std::atomic<uint32_t> frane_interval { 2 };''',
'''   std::atomic<uint32_t> frane_interval { 2 };
   frane_2634_gmem_state frane_gmem_runtime_state {};
   std::atomic<uint32_t> frane_gmem_runtime_word { 0 };''',
"per-RP submit-owned runtime state plus atomic snapshot")

# Extend the PROFILED decision function with optional per-recording layout data.
edit("src/freedreno/vulkan/tu_autotune.cc",
'''      render_mode get_optimal_mode(rp_history &history, bool *measure = nullptr,
                                   bool lean_fastpath = false)
      {''',
'''      render_mode get_optimal_mode(
         rp_history &history, bool *measure = nullptr,
         bool lean_fastpath = false,
         const frane_2634_gmem_layout_input *gmem_runtime_input = nullptr)
      {''',
"PROFILED accepts optional GMEM runtime layout")

old = '''         const bool definite = measure && lean_fastpath &&
            frane_v24_is_definite(l_sysmem_probability);
         const bool select_sysmem = definite
            ? frane_v24_definite_sysmem(l_sysmem_probability)
            : (frane_2633_decision_draw(history.hash) % PROBABILITY_MAX) <
                 l_sysmem_probability;
         const render_mode mode =
            select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;

         if (measure) {
            if (definite) {'''
new = '''         const bool definite = measure && lean_fastpath &&
            frane_v24_is_definite(l_sysmem_probability);
         const uint64_t decision_word =
            definite ? 0 : frane_2633_decision_draw(history.hash);
         bool select_sysmem = definite
            ? frane_v24_definite_sysmem(l_sysmem_probability)
            : (decision_word % PROBABILITY_MAX) < l_sysmem_probability;

         bool runtime_force_measure = false;
         if (!definite && measure && lean_fastpath && gmem_runtime_input) {
            const auto layout = frane_2634_eval_layout(*gmem_runtime_input);
            const auto runtime_state = frane_2634_unpack_gmem_state(
               history.frane_gmem_runtime_word.load(std::memory_order_relaxed));
            const auto runtime_decision = frane_2634_decide_gmem_runtime(
               gmem_runtime_input->physical_gmem != 0,
               layout.eligible, runtime_state,
               l_sysmem_probability, decision_word);
            if (runtime_decision.override_mode) {
               select_sysmem = runtime_decision.select_sysmem;
               runtime_force_measure = runtime_decision.force_measure;
            }
         }

         const render_mode mode =
            select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;

         if (measure) {
            if (runtime_force_measure) {
               *measure = true;
            } else if (definite) {'''
edit("src/freedreno/vulkan/tu_autotune.cc", old, new,
     "hysteretic GMEM promotion with measured SYSMEM probes")

# Submit-side runtime state: only timing results change confidence. This is
# intentionally after profiled.update() so it sees the newest EMA values.
old = '''            const uint64_t sys = sysmem_rp_average.get();
            const uint64_t gm = gmem_rp_average.get();
            const uint32_t sample_base = frane_2632_profile_base_interval('''
new = '''            const uint64_t sys = sysmem_rp_average.get();
            const uint64_t gm = gmem_rp_average.get();

            if (frane_a810_gmem_runtime_enabled(at.device)) {
               frane_gmem_runtime_state = frane_2634_update_gmem_state(
                  frane_gmem_runtime_state, sys, gm,
                  sysmem_rp_average.count, gmem_rp_average.count);
               frane_gmem_runtime_word.store(
                  frane_2634_pack_gmem_state(frane_gmem_runtime_state),
                  std::memory_order_relaxed);
            }

            const uint32_t sample_base = frane_2632_profile_base_interval('''
edit("src/freedreno/vulkan/tu_autotune.cc", old, new,
     "publish measured runtime confidence on submit thread")

# Construct cheap layout metadata only in the existing one-time-CB PROFILED
# path. No GMEM allocation/layout/registers are modified.
old = '''      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath());
      if (measure)'''
new = '''      frane_2634_gmem_layout_input runtime_input {};
      if (frane_a810_gmem_runtime_enabled(device)) {
         uint64_t pass_pixels = 0;
         if (cmd_state->per_layer_render_area) {
            for (unsigned i = 0; i < cmd_state->pass->num_views; i++) {
               const VkExtent2D &extent = cmd_state->render_areas[i].extent;
               pass_pixels += uint64_t(extent.width) * extent.height;
            }
         } else {
            const VkExtent2D &extent = cmd_state->render_areas[0].extent;
            pass_pixels = uint64_t(extent.width) * extent.height *
               MAX2(cmd_state->pass->num_views, cmd_state->framebuffer->layers);
         }

         runtime_input.physical_gmem = device->physical_device->gmem_size;
         runtime_input.usable_gmem =
            device->physical_device->usable_gmem_size_gmem;
         runtime_input.pixels_per_tile =
            pass->gmem_pixels[TU_GMEM_LAYOUT_FULL];
         runtime_input.pass_pixels = pass_pixels;
         runtime_input.drawcalls = rp_state->drawcall_count;
      }

      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.physical_gmem ? &runtime_input : nullptr);
      if (measure)'''
edit("src/freedreno/vulkan/tu_autotune.cc", old, new,
     "feed real Mesa FULL-layout metadata to runtime")

# Assert the runtime does not replace the primary algorithm or old V28-CLEAN
# rollback: A810 remains on PROFILED, and the old custom BANDWIDTH flag stays off.
a = (V / "tu_autotune.cc").read_text()
for needle in (
   'algo_strv = "profiled";',
   'return a830;',
   'frane_2634_decide_gmem_runtime',
   'TU_A810_GMEM_RUNTIME',
   'TU_GMEM_LAYOUT_FULL',
):
    if needle not in a:
        raise SystemExit(f"26.3.4 missing runtime prerequisite: {needle}")
print("26.3.4 GMEM-RUNTIME PASS PROFILED remains primary / old BANDWIDTH runtime stays disabled", flush=True)

edit("src/freedreno/vulkan/tu_device.cc",
     "Frane Mesa 26.3.3 A810 PROFILE-TURBO EXP / Mesa ",
     "Frane Mesa 26.3.4 A810 GMEM-RUNTIME EXP / Mesa ",
     "experimental driver identity")

print("Frane Mesa 26.3.4 A810 GMEM-RUNTIME EXP applied", flush=True)
