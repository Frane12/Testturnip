#!/usr/bin/env python3
"""Drnas-Turnip S1 AT1 A810 CONTEXTUAL-AUTOTUNE.

Layered strictly on the public S1 source stack.

AT1 adds a never-locking contextual learner around S1:
  * workload catalogs from pixels/tiles/draw density/depth/replay/bandwidth;
  * bandwidth is only admitted as a prior when the workload is large enough;
  * robust EW mean + EW absolute deviation on measured GMEM/SYSMEM timings;
  * bounded residual CUSUM for scene/regime-change detection;
  * empirical-Bayes-style shrinkage of noisy/low-sample timing advantages;
  * live Mesa PROFILED probability remains the dynamic base signal;
  * uncertainty-driven measurement cadence with a finite exploration floor.

TU_FRANE_AT1=0 restores exact S1 policy in the same binary.

No GMEM layout/offset, attachment programming, LRZ, barriers, shaders,
concurrent-binning, WSI or Vulkan synchronization changes.
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
        raise SystemExit(
            f"S1 AT1 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"S1 AT1 PASS {label}", flush=True)


shutil.copyfile(
    "patches/frane_s1at1_contextual_autotune.h",
    V / "frane_s1at1_contextual_autotune.h",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '#include "frane_mesa_26320_a810_gmem_turbo.h"',
    '#include "frane_mesa_26320_a810_gmem_turbo.h"\n'
    '#include "frane_s1at1_contextual_autotune.h"',
    "include contextual policy",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_s1at1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_AT1", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{""",
    "add A810 AT1 gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   bool sysmem;
   uint32_t tile_count;
   uint32_t draw_count;""",
    """   bool sysmem;
   uint32_t tile_count;
   uint32_t draw_count;
   uint16_t frane_s1at1_signature = 0;""",
    "carry exact contextual signature with measured RP entry",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   std::atomic<uint32_t> frane_tail_occurrences { 0 };""",
    """   std::atomic<uint32_t> frane_tail_occurrences { 0 };

   /* S1 AT1: submit-thread-owned robust statistics, compact atomic snapshot
    * read by recording threads. No lock bit exists by design.
    */
   frane_s1at1_state frane_s1at1_state_data {};
   std::atomic<uint32_t> frane_s1at1_word { 0 };""",
    "add per-RP AT1 statistics",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            frane_tail_scan_word.store(
               frane_26359_pack_scan(
                  frane_tail_state.sysmem.samples,
                  frane_tail_state.gmem.samples),
               std::memory_order_relaxed);
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {""",
    """            frane_tail_scan_word.store(
               frane_26359_pack_scan(
                  frane_tail_state.sysmem.samples,
                  frane_tail_state.gmem.samples),
               std::memory_order_relaxed);
         }

         if (frane_a810_s1at1_enabled(at.device)) {
            frane_s1at1_state_data = frane_s1at1_update_state(
               frane_s1at1_state_data, entry.sysmem, rp_duration,
               entry.frane_s1at1_signature);
            frane_s1at1_word.store(
               frane_s1at1_pack_snapshot(frane_s1at1_state_data),
               std::memory_order_relaxed);
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {""",
    "update AT1 only from measured GPU RP durations",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         bool gmem_turbo = false,
         bool live_profiled = false)
      {""",
    """         bool gmem_turbo = false,
         bool live_profiled = false,
         bool s1at1_context = false)
      {""",
    "extend PROFILED decision with AT1 gate",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """               runtime_decision.override_mode = smart_decision.override_mode;
               runtime_decision.select_sysmem = smart_decision.select_sysmem;
               runtime_decision.force_measure = smart_decision.force_measure;""",
    """               runtime_decision.override_mode = smart_decision.override_mode;
               runtime_decision.select_sysmem = smart_decision.select_sysmem;
               runtime_decision.force_measure = smart_decision.force_measure;

               /* AT1 is an overlay, not a replacement for S1. Compute S1 first,
                * then let contextual evidence overwrite only when it is active.
                * TU_FRANE_AT1=0 therefore leaves byte-identical S1 decisions.
                */
               if (s1at1_context) {
                  const auto at1_snapshot = frane_s1at1_unpack_snapshot(
                     history.frane_s1at1_word.load(std::memory_order_relaxed));

                  frane_s1at1_context_input at1_in {};
                  at1_in.pass_pixels = gmem_runtime_input->layout.pass_pixels;
                  at1_in.estimated_tiles = layout.estimated_tiles;
                  at1_in.drawcalls = gmem_runtime_input->layout.drawcalls;
                  at1_in.sysmem_bandwidth_per_pixel =
                     gmem_runtime_input->sysmem_bandwidth_per_pixel;
                  at1_in.gmem_bandwidth_per_pixel =
                     gmem_runtime_input->gmem_bandwidth_per_pixel;
                  at1_in.occurrences = gmem_runtime_input->tail_occurrences;
                  at1_in.sysmem_probability = l_sysmem_probability;
                  at1_in.zs_load_store = gmem_runtime_input->zs_load_store;

                  const auto at1 = frane_s1at1_decide(
                     true, at1_in, at1_snapshot, decision_word);

                  if (at1.override_mode) {
                     runtime_decision.override_mode = true;
                     runtime_decision.select_sysmem = at1.select_sysmem;
                     runtime_decision.force_measure = at1.force_measure;
                  }
               }""",
    "overlay contextual policy on exact S1 decision",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device),
         frane_a810_gmem_turbo_enabled(device),
         frane_a810_live_profiled(device));""",
    """      if (frane_a810_s1at1_enabled(device) &&
          runtime_input.layout.physical_gmem && *rp_ctx) {
         const auto layout = frane_2634_eval_layout(runtime_input.layout);
         frane_s1at1_context_input at1_in {};
         at1_in.pass_pixels = runtime_input.layout.pass_pixels;
         at1_in.estimated_tiles = layout.estimated_tiles;
         at1_in.drawcalls = runtime_input.layout.drawcalls;
         at1_in.sysmem_bandwidth_per_pixel =
            runtime_input.sysmem_bandwidth_per_pixel;
         at1_in.gmem_bandwidth_per_pixel =
            runtime_input.gmem_bandwidth_per_pixel;
         at1_in.occurrences = runtime_input.tail_occurrences;
         at1_in.sysmem_probability = 50;
         at1_in.zs_load_store = runtime_input.zs_load_store;
         (*rp_ctx)->frane_s1at1_signature =
            frane_s1at1_catalog_for(at1_in).signature;
      }

      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_a810_smart_gmem_enabled(device),
         frane_a810_gmem_turbo_enabled(device),
         frane_a810_live_profiled(device),
         frane_a810_s1at1_enabled(device));""",
    "attach exact catalog signature and enable AT1",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas-Turnip S1 A810 / Mesa ",
    "Drnas-Turnip S1 AT1 A810 / Mesa ",
    "AT1 display identity",
)

a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
p = (V / "tu_pass.cc").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_AT1", true',
    "frane_s1at1_state_data",
    "frane_s1at1_word",
    "entry.frane_s1at1_signature",
    "frane_s1at1_update_state",
    "frane_s1at1_decide",
    "frane_s1at1_catalog_for",
    "bool s1at1_context = false",
):
    assert needle in a, needle

# Exact S1 remains the first rollback path.
assert "frane_26320_decide_gmem_turbo" in a
assert "frane_26318_decide_smart_gmem" in a
assert 'TU_FRANE_SIG", true' in a
assert 'TU_FRANE_FREQ", true' in a
assert 'TU_FRANE_SCAN", true' in a
assert 'TU_FRANE_LEARN", true' in a
assert 'TU_FRANE_TAIL", true' in a

# Keep S1's never-locking Mesa PROFILED path and safety-sensitive layers.
assert "if (live_profiled && !immediate)" in a
assert "locked = false;" in a
assert "TU_FRANE_GMEM_PRESSURE" in p
assert "TU_FRANE_CB_MODE" in c
assert "subpass.resolve_depth_stencil" in a
assert "subpass.feedback_loop_ds" in a
assert "subpass.samples != VK_SAMPLE_COUNT_1_BIT" in a
assert "Drnas-Turnip S1 AT1 A810 / Mesa " in d

print("Drnas-Turnip S1 AT1 CONTEXTUAL-AUTOTUNE applied", flush=True)
