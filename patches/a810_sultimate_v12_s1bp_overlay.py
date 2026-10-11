#!/usr/bin/env python3
"""S Ultimate v1.2 sampled buffered S1 profiling over pinned v1.1."""
from pathlib import Path
import shutil
V=Path("mesa/src/freedreno/vulkan")
auto=V/"tu_autotune.cc"
dev=V/"tu_device.cc"
shutil.copyfile("patches/frane_a810_s1_bandwidth_probe.h",V/"frane_a810_s1_bandwidth_probe.h")
def change(p,old,new,name):
    s=p.read_text()
    n=s.count(old)
    if n!=1:
        raise SystemExit(f"v1.2 S1BP SOURCE DRIFT {name}: {n}")
    p.write_text(s.replace(old,new,1))
    print("v1.2 S1BP PASS",name,flush=True)

change(auto,'#include "frane_a810_atultimate_trace.h"',
       '#include "frane_a810_atultimate_trace.h"\n#include "frane_a810_s1_bandwidth_probe.h"',
       "include logger")
change(auto,
'''frane_atu_v3_result *atu_v3_diag = nullptr)''',
'''frane_atu_v3_result *atu_v3_diag = nullptr,
         bool *s1_override_out = nullptr,
         bool *s1_sysmem_out = nullptr)''',
       "S1 provenance parameters")
change(auto,
'''            if (s1at1_context) {''',
'''            /* Record the S1 result before later AT1/AT4/V3 stages.
             * No change to selection, sampling, or synchronization.
             */
            if (s1_override_out)
               *s1_override_out = runtime_decision.override_mode;
            if (s1_sysmem_out)
               *s1_sysmem_out = runtime_decision.select_sysmem;
            if (s1at1_context) {''',
       "S1 candidate snapshot")
change(auto,
'''      bool atu_v3_applied = false;
      frane_atu_v3_result atu_v3_diag {};''',
'''      bool atu_v3_applied = false;
      bool s1_runtime_override = false;
      bool s1_runtime_sysmem = false;
      frane_atu_v3_result atu_v3_diag {};''',
       "optional provenance storage")
change(auto,
'''         v3 && context_eligible, &atu_v3_applied,
         &atu_v3_diag);''',
'''         v3 && context_eligible, &atu_v3_applied,
         &atu_v3_diag,
         &s1_runtime_override, &s1_runtime_sysmem);''',
       "pass S1 provenance pointers")
change(auto,
'''         frane_atu_trace(row,history.frane_s1at3_words);
      }
      return mode;''',
'''         frane_atu_trace(row,history.frane_s1at3_words);
      }
      const uint64_t s1bp_seq = frane_s1bp_take_sample();
      if (s1bp_seq) {
         /* Attachment byte estimates are not physical DRAM counters.
          * Zero cpp is UNKNOWN; do not interpret as zero traffic. */
         const auto ev = frane_26318_eval_smart_gmem(runtime_input);
         const auto rs = frane_2634_unpack_gmem_state(
            history.frane_gmem_runtime_word.load(std::memory_order_relaxed));
         frane_s1at1_context_input ci {};
         ci.pass_pixels = runtime_input.layout.pass_pixels;
         ci.estimated_tiles = ev.estimated_tiles;
         ci.drawcalls = runtime_input.layout.drawcalls;
         ci.sysmem_bandwidth_per_pixel = runtime_input.sysmem_bandwidth_per_pixel;
         ci.gmem_bandwidth_per_pixel = runtime_input.gmem_bandwidth_per_pixel;
         ci.occurrences = runtime_input.tail_occurrences;
         ci.sysmem_probability = history.profiled.probability();
         ci.zs_load_store = runtime_input.zs_load_store;
         const auto cat = frane_s1at1_catalog_for(ci);
         const auto snap = frane_s1at3_lookup(
            history.frane_s1at3_words,cat.signature);
         frane_s1bp_row bp {};
         bp.rp_hash = history.hash;
         bp.pixels = ci.pass_pixels;
         bp.tiles = ev.estimated_tiles;
         bp.drawcalls = ci.drawcalls;
         bp.sys_cpp = ci.sysmem_bandwidth_per_pixel;
         bp.gmem_cpp = ci.gmem_bandwidth_per_pixel;
         bp.zs = ci.zs_load_store;
         bp.eligible = ev.eligible && context_eligible;
         bp.structure_score = ev.structure_score;
         bp.runtime_armed = rs.armed;
         bp.runtime_score = rs.score;
         bp.profiled_sys_pct = ci.sysmem_probability;
         bp.s1_override = s1_runtime_override;
         bp.s1_sysmem = s1_runtime_sysmem;
         bp.final_sysmem = mode == render_mode::SYSMEM;
         bp.measure = measure;
         bp.at4_probe = at3_controlled && measure;
         bp.v3_used = atu_v3_applied;
         bp.at3_score = snap.signature == cat.signature ? int(snap.score) : 0;
         bp.at3_pairs = snap.signature == cat.signature ?
            std::min(snap.samples[0],snap.samples[1]) : 0;
         bp.at3_noise_q8 = snap.signature == cat.signature ?
            snap.at7_noise_q8 : 0;
         bp.final_source = safety_forced ? "GMEM_SAFETY" :
            depth_overrode ? "DEPTH_FRONTIER" :
            atu_v3_applied ? "ATU_V3_CATEGORY_WINNER" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :
            at7_applied ? "AT7_UTILITY_WINNER" :
            at63_applied ? "AT63_EARLY_WINNER" :
            at6_applied ? "AT6_AT4BASE" :
            at4_applied ? "AT4_OVERRIDE" :
            at3_controlled ? "AT3_CONTEXT" :
            s1_runtime_override ? "S1_OR_AT1" : "PROFILED_OR_AT1";
         frane_s1bp_trace(s1bp_seq,bp);
      }
      return mode;''',
       "post-safety sampled trace")
change(dev,'Drnas-Turnip A810 S Ultimate v1.1 / Mesa ',
       'Drnas-Turnip A810 S Ultimate v1.2 / Mesa ',
       "Vulkan driverInfo")
change(dev,'"Drnas-Turnip A810 S Ultimate v1.1" : pdevice->name',
       '"Drnas-Turnip A810 S Ultimate v1.2" : pdevice->name',
       "DXVK adapter name")
print("S Ultimate v1.2 S1 bandwidth probe source overlay PASS")
