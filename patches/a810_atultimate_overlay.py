#!/usr/bin/env python3
"""ATUltimate A810 overlay AFTER AT7/CP1/AT8. No AT9 code or FC2 forced prior.
Reuse 16-entry associative AT3 GPU history; add guarded heuristic rejection and
independent sampled CSV of actual final (post-depth/safety) decisions and table.
"""
from pathlib import Path
import shutil
V=Path("mesa/src/freedreno/vulkan")
auto=V/"tu_autotune.cc"
dev=V/"tu_device.cc"
def edit(path,old,new,label):
    s=path.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"ATUltimate SOURCE DRIFT {label}: {n}")
    path.write_text(s.replace(old,new,1))
    print("ATUltimate PASS",label,flush=True)

for name in ("frane_a810_atultimate.h","frane_a810_atultimate_trace.h"):
    shutil.copyfile("patches/"+name,V/name)
edit(auto, '#include "frane_a810_at8_early.h"',
     '#include "frane_a810_at8_early.h"\n#include "frane_a810_atultimate_trace.h"',
     "use existing packed snapshot table and sampled logger")
edit(auto,
"""static bool frane_a810_at8_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT8", true);
   return on && frane_a810_at7_enabled(d);
}""",
"""static bool frane_a810_at8_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT8", true);
   return on && frane_a810_at7_enabled(d);
}
static bool frane_a810_atu_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_ATU", true);
   return on && frane_a810_at8_enabled(d);
}""","reversible A810-only default ON policy toggle")
edit(auto,
"""   std::atomic<uint32_t> frane_a810_rfc_occurrence { 0 };""",
"""   std::atomic<uint32_t> frane_a810_rfc_occurrence { 0 };
   /* Independent context-table sequence, increments ONLY when enabled. */
   std::atomic<uint32_t> frane_atu_occurrence { 0 };""",
     "add optional per-RP-history context table sequence")
edit(auto,
"""         bool s1at8_context = false, bool *at8_applied = nullptr)""",
"""         bool s1at8_context = false, bool *at8_applied = nullptr,
         bool s1atu_context = false, bool *atu_prior_rejected = nullptr)""",
     "pass bounded confidence guard to true selector runtime")
edit(auto,
"""                     if (prior.override_mode) {
                        if (at6_applied) *at6_applied = true;
                        select_sysmem = prior.select_sysmem;
                     }
                  }
                  at3_sampling = at1.override_mode;""",
"""                     /* ATUltimate only BLOCKS a contradictory heuristic,
                      * never locks a GPU mode or bypasses AT4 exploration. */
                     bool rejected = false;
                     const auto adjusted = s1atu_context ?
                        frane_atu_protect_prior(at1_in, snapshot, at1,
                                                prior, &rejected) : prior;
                     if (rejected && atu_prior_rejected)
                        *atu_prior_rejected = true;
                     if (adjusted.override_mode) {
                        if (at6_applied) *at6_applied = true;
                        select_sysmem = adjusted.select_sysmem;
                     }
                  }
                  at3_sampling = at1.override_mode;""",
     "protect real GPU paired measurements from wrong-way AT6 heuristics")
edit(auto,
"""      const bool at8 = frane_a810_at8_enabled(device);
      const bool context_eligible = !at4 ||""",
"""      const bool at8 = frane_a810_at8_enabled(device);
      const bool atu = frane_a810_atu_enabled(device);
      const bool context_eligible = !at4 ||""",
     "A810 ATUltimate only when valid AT8 rendering context")
edit(auto,
"""      bool at8_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
"""      bool at8_applied = false;
      bool atu_prior_rejected = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     "separate GPU history guard provenance")
edit(auto,
"""         at8 && context_eligible, &at8_applied);""",
"""         at8 && context_eligible, &at8_applied,
         atu && context_eligible, &atu_prior_rejected);""",
     "connect actual selector to history guard; zero-cost when disabled")
edit(auto,
"""      const bool trace_rfc1 = frane_a810_gpu(device) && frane_a810_rfc1_path();""",
"""      const bool trace_rfc1 = frane_a810_gpu(device) && frane_a810_rfc1_path();
      const bool trace_atu = frane_a810_gpu(device) && frane_atu_trace_path();
      const uint32_t atu_occurrence = trace_atu ?
         history.frane_atu_occurrence.fetch_add(
            1, std::memory_order_relaxed) + 1u : 0u;""",
     "optional context CSV without enabling heavy RFC1 logger")
edit(auto,
"""         const char *source = safety_forced ? "GMEM_SAFETY" :
            depth_overrode ? "DEPTH_FRONTIER" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :""",
"""         const char *source = safety_forced ? "GMEM_SAFETY" :
            depth_overrode ? "DEPTH_FRONTIER" :
            atu_prior_rejected ? "ATU_HISTORY_GUARD" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :""",
     "attribution in preexisting RFC1 GPU CSV")
edit(auto,
"""            runtime_input.layout.usable_gmem);
      }
      return mode;""",
"""            runtime_input.layout.usable_gmem);
      }
      if (trace_atu) {
         const auto layout = frane_2634_eval_layout(runtime_input.layout);
         frane_s1at1_context_input context {};
         context.pass_pixels = runtime_input.layout.pass_pixels;
         context.estimated_tiles = layout.estimated_tiles;
         context.drawcalls = runtime_input.layout.drawcalls;
         context.sysmem_bandwidth_per_pixel =
            runtime_input.sysmem_bandwidth_per_pixel;
         context.gmem_bandwidth_per_pixel =
            runtime_input.gmem_bandwidth_per_pixel;
         context.occurrences = runtime_input.tail_occurrences;
         context.sysmem_probability = history.profiled.probability();
         context.zs_load_store = runtime_input.zs_load_store;
         const uint16_t signature =
            runtime_input.layout.physical_gmem && context_eligible ?
            frane_s1at1_catalog_for(context).signature : 0;
         const auto snapshot = signature ?
            frane_s1at3_lookup(history.frane_s1at3_words,signature) :
            frane_s1at3_snapshot{};
         frane_atu_trace_row row {};
         row.hash = history.hash;
         row.occurrence = atu_occurrence;
         row.signature = signature;
         row.in = context;
         row.s = snapshot;
         row.probability = history.profiled.probability();
         row.mode_sysmem = mode == render_mode::SYSMEM;
         row.measure = measure;
         row.eligible = context_eligible;
         row.safety_forced = safety_forced;
         row.depth_overrode = depth_overrode;
         row.at4_controlled = at3_controlled;
         row.prior_rejected = atu_prior_rejected;
         row.source = safety_forced ? "GMEM_SAFETY" :
            depth_overrode ? "DEPTH_FRONTIER" :
            atu_prior_rejected ? "ATU_HISTORY_GUARD" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :
            at7_applied ? "AT7_UTILITY_WINNER" :
            at63_applied ? "AT63_EARLY_WINNER" :
            at6_applied ? "AT6_AT4BASE" :
            at4_applied ? "AT4_OVERRIDE" :
            at3_controlled ? "AT3_CONTEXT" : "PROFILED_OR_S1";
         frane_atu_trace(row,history.frane_s1at3_words);
      }
      return mode;""",
     "emit real final choice plus atomic context TABLE snapshot, opt-in only")
edit(dev, "Drnas-Turnip A810 AT8 Early GPU Winner / Mesa ",
          "Drnas-Turnip A810 ATUltimate Context Learner / Mesa ",
     "Vulkan driverInfo identifies actual ATUltimate binary")
s=auto.read_text()
for x in ("TU_FRANE_ATU", "TU_FRANE_ATU_CONTEXT_TRACE_PATH" if False else "frane_atu_trace_path()",
          "frane_atu_protect_prior(", "frane_atu_trace(row,history.frane_s1at3_words)",
          "atu && context_eligible", "TU_FRANE_AT8",
          "frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)",
          "frane_a810_rfc1_decision("):
    assert x in s,x
assert s.index("frane_atu_protect_prior(") < s.index("at3_sampling = at1.override_mode;")
assert s.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") < s.index("frane_atu_trace(row,history.frane_s1at3_words)")
assert not any(x in s for x in ("TU_FRANE_AT9","frane_at9_fc2","AT9_FC2_PRIOR"))
print("ATUltimate A810 final selector, AT8 parity, AT9 exclusion, safety and diagnostics PASS")
