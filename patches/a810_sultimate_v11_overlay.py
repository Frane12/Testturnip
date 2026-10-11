#!/usr/bin/env python3
"""S Ultimate v1.1: strong vetoes for probe, runtime sampling and GMEM correctness."""
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
h=V/"frane_a810_atultimate_v3.h"
a=V/"tu_autotune.cc"
d=V/"tu_device.cc"
def change(path,old,new,tag):
 s=path.read_text()
 n=s.count(old)
 if n!=1: raise SystemExit(f"v1.1 SOURCE DRIFT {tag}: {n}")
 path.write_text(s.replace(old,new,1))
 print("v1.1 PASS",tag,flush=True)
change(h,"   ATU_V3_RUNTIME_PRIORITY,\n   ATU_V3_READY,","   ATU_V3_RUNTIME_PRIORITY,\n   ATU_V3_SAFETY_VETO,\n   ATU_V3_READY,","enum")
change(h,'   case ATU_V3_RUNTIME_PRIORITY: return "RUNTIME_PRIORITY";','   case ATU_V3_RUNTIME_PRIORITY: return "RUNTIME_PRIORITY";\n   case ATU_V3_SAFETY_VETO: return "SAFETY_VETO";',"reason")
change(h,"                   unsigned stable_hits, unsigned dwell)\n","                   unsigned stable_hits, unsigned dwell,\n                   bool safety_ok = true)\n","API hard safety")
change(h,
"""       else if (!may_override) {
          out.blocked = true;
          out.why = at4_probe ? ATU_V3_AT4_PROBE :
             runtime_override ? ATU_V3_RUNTIME_PRIORITY : ATU_V3_AT4_PRIORITY;
       } else {""",
"""       else if (!safety_ok) {
          out.blocked = true;
          out.why = ATU_V3_SAFETY_VETO;
       } else if (!may_override || at4_probe || runtime_override) {
          /* Probe and runtime vetoes must work even if the caller accidentally
           * claims an override is allowed. Keep learning while vetoed. */
          out.blocked = true;
          out.why = at4_probe ? ATU_V3_AT4_PROBE :
             runtime_override ? ATU_V3_RUNTIME_PRIORITY : ATU_V3_AT4_PRIORITY;
       } else {""","hard veto")
change(a,
"""                  if (s1atu_v3_context && s1at4_context) {
                      const auto v3 = frane_atu_v3_step(""",
"""                  if (s1atu_v3_context && s1at4_context) {
                      /* AT4 gates per-pass GMEM correctness. If the user
                       * disables that correctness gate, V3 cannot select. */
                      static const bool v3_safe_enabled =
                         debug_get_bool_option("TU_FRANE_GMEM_SAFE", true);
                      const bool v3_safe = v3_safe_enabled &&
                         frane_2634_eval_layout(
                            gmem_runtime_input->layout).eligible;
                      const auto v3 = frane_atu_v3_step(""","GMEM safety/layout check")
change(a,
"""                         !at1.override_mode && !runtime_decision.override_mode,
                         at1.force_measure,runtime_decision.override_mode,
                         frane_a810_atu_fast_enabled(),
                         frane_a810_atu_phase_hits(),frane_a810_atu_dwell());""",
"""                         !at1.override_mode && !at1.force_measure &&
                            !runtime_decision.override_mode &&
                            !runtime_decision.force_measure,
                         at1.force_measure,
                         runtime_decision.override_mode ||
                            runtime_decision.force_measure,
                         frane_a810_atu_fast_enabled(),
                         frane_a810_atu_phase_hits(),frane_a810_atu_dwell(),
                         v3_safe);""","runtime veto")
change(d,"Drnas-Turnip A810 S Ultimate v1.0","Drnas-Turnip A810 S Ultimate v1.1","branding")
print("S Ultimate v1.1 guard audit PASS")
