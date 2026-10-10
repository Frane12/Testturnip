#!/usr/bin/env python3
"""RFC1 on tested BW2: one BW2 eval per actual SMART/PROFILED decision.
Opt-in read-only CSV trace, preserving exact rp_key and A830 GMEM safety.
"""
from pathlib import Path
import hashlib, shutil

ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*") if p.is_file()}

def edit(path,old,new,label):
    s=path.read_text()
    n=s.count(old)
    if n!=1: raise SystemExit(f"RFC1 collision/drift {label}: {n} anchors")
    path.write_text(s.replace(old,new,1))
    print(f"RFC1 PASS {label}",flush=True)

shutil.copyfile("patches/frane_a830_rfc1.h", V/"frane_a830_rfc1.h")
smart=V/"frane_mesa_26318_a810_smart_gmem.h"
edit(smart,
     "   bool a830_bw2 = false;",
     """   bool a830_bw2 = false;
   bool a830_rfc1 = false;
   bool a830_rfc_has_cache = false;
   frane_a830_s2bw2_eval a830_rfc_cached_bw2 {};
""".rstrip(),
     "cache fields on existing per-decision input")

edit(smart,
     "      const auto bw2 = frane_a830_s2bw2_evaluate(",
     "      const auto bw2 = in.a830_rfc_has_cache ? in.a830_rfc_cached_bw2 : frane_a830_s2bw2_evaluate(",
     "reuse BW2 eval in SMART scoring")

adaptive=V/"frane_a830_v2_adaptive_gmem.h"
edit(adaptive,
     "      const auto bw2 = frane_a830_s2bw2_evaluate(",
     "      const auto bw2 = in.a830_rfc_has_cache ? in.a830_rfc_cached_bw2 : frane_a830_s2bw2_evaluate(",
     "reuse identical BW2 eval in measured-history rollback")

auto=V/"tu_autotune.cc"
edit(auto,
     '#include "frane_mesa_26318_a810_smart_gmem.h"',
     '#include "frane_mesa_26318_a810_smart_gmem.h"\n#include "frane_a830_rfc1.h"',
     "include RFC1 trace helper")

edit(auto,
     """         bool runtime_force_measure = false;
         if (!definite && measure && lean_fastpath && gmem_runtime_input) {
            const auto runtime_state = frane_2634_unpack_gmem_state(""",
     """         /* Only evaluate BW2 once when the normal SM/PROFILED decision
          * needs it, AFTER the earlier frane_smart/definite shortcuts.
          * Never share an evaluation between RPs or across history updates.
          */
         frane_26318_smart_gmem_input rfc1_input {};
         if (!definite && measure && lean_fastpath && smart_gmem &&
             gmem_runtime_input && gmem_runtime_input->a830_bw2 &&
             gmem_runtime_input->a830_rfc1) {
            rfc1_input = *gmem_runtime_input;
            rfc1_input.a830_rfc_cached_bw2 = frane_a830_s2bw2_evaluate(
               rfc1_input.layout.pass_pixels,
               rfc1_input.selected_tile_pixels,
               rfc1_input.allocator_capacity_pixels,
               rfc1_input.layout.drawcalls,
               rfc1_input.sysmem_bandwidth_per_pixel,
               rfc1_input.gmem_bandwidth_per_pixel,
               rfc1_input.peak_live_cpp,
               uint32_t(std::min<uint64_t>(
                  rfc1_input.layout.usable_gmem, UINT32_MAX)),
               rfc1_input.peak_live_planes,
               rfc1_input.a830_history_score,
               rfc1_input.a830_history_pairs,
               rfc1_input.a830_history_ready,
               rfc1_input.a830_measured_score,
               rfc1_input.a830_measured_armed);
            rfc1_input.a830_rfc_has_cache = true;
            gmem_runtime_input = &rfc1_input;
         }

         bool runtime_force_measure = false;
         if (!definite && measure && lean_fastpath && gmem_runtime_input) {
            const auto runtime_state = frane_2634_unpack_gmem_state(""",
     "lazy, per-decision one-shot BW2 memo, no stale cross-pass cache")

edit(auto,
     """static bool
frane_a830_s2bw2_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW2", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     """static bool
frane_a830_s2bw2_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW2", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_rfc1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC1", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     "A830-only RFC1 A/B gate")

edit(auto,
     """         runtime_input.a830_bw2 =
            frane_a830_s2bw2_enabled(device);

         if (runtime_input.a830_bw2) {""",
     """         runtime_input.a830_bw2 =
            frane_a830_s2bw2_enabled(device);
         runtime_input.a830_rfc1 =
            runtime_input.a830_bw2 && frane_a830_rfc1_enabled(device);

         if (runtime_input.a830_bw2) {""",
     "enable RFC1 only for BW2 and exact A830")

edit(auto,
     """      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_26320_a830_smart_gmem_enabled(device),
         frane_a830_v2_flags(device), smart, occurrence, tail_risk);
      if (measure) {""",
     """      const render_mode mode = history.profiled.get_optimal_mode(
         history, &measure, frane_a810_v24_fastpath(),
         runtime_input.layout.physical_gmem ? &runtime_input : nullptr,
         frane_26320_a830_smart_gmem_enabled(device),
         frane_a830_v2_flags(device), smart, occurrence, tail_risk);
      /* Read-only diagnostic: 1/64 occurrences; no file I/O without path.
       * Show the actual final rendering mode, not a speculative prior.
       */
      if (runtime_input.a830_bw2 && frane_a830_rfc1_trace_path() &&
          ((occurrence - 1u) & 63u) == 0u) {
         frane_26318_smart_gmem_input trace_input = runtime_input;
         trace_input.a830_rfc_cached_bw2 = frane_a830_s2bw2_evaluate(
            trace_input.layout.pass_pixels, trace_input.selected_tile_pixels,
            trace_input.allocator_capacity_pixels, trace_input.layout.drawcalls,
            trace_input.sysmem_bandwidth_per_pixel,
            trace_input.gmem_bandwidth_per_pixel, trace_input.peak_live_cpp,
            uint32_t(std::min<uint64_t>(
               trace_input.layout.usable_gmem, UINT32_MAX)),
            trace_input.peak_live_planes, trace_input.a830_history_score,
            trace_input.a830_history_pairs, trace_input.a830_history_ready,
            trace_input.a830_measured_score, trace_input.a830_measured_armed);
         trace_input.a830_rfc_has_cache = true;
         frane_a830_rfc1_trace(
            history.hash, occurrence, trace_input,
            mode == render_mode::SYSMEM, measure);
      }
      if (measure) {""",
     "sample mode and structural signature to user-specified CSV only")

edit(V/"tu_device.cc",
     "Turnip-Drnas A830 S2-BW2 Adaptive Tile Cost / Mesa ",
     "Turnip-Drnas A830 S2-RFC1 Render Features / Mesa ",
     "driver identity")

for path in (smart,adaptive,auto):
    s=path.read_text()
    assert "a830_rfc_cached_bw2" in s
assert 'TU_FRANE_A830_RFC1", true' in auto.read_text()
assert 'TU_FRANE_A830_TRACE_PATH' in (V/"frane_a830_rfc1.h").read_text()
assert "Turnip-Drnas A830 S2-RFC1 Render Features / Mesa " in (V/"tu_device.cc").read_text()
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in ROOT.rglob("*") if p.is_file()}
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={
   "vulkan/frane_a830_rfc1.h",
   "vulkan/frane_mesa_26318_a810_smart_gmem.h",
   "vulkan/frane_a830_v2_adaptive_gmem.h",
   "vulkan/tu_autotune.cc",
   "vulkan/tu_device.cc",
}
if changed!=expected:
    raise SystemExit(f"RFC1 unexpected source scope {sorted(changed ^ expected)}")
print("A830 RFC1 structural cache/trace integration and source scope PASS",flush=True)
