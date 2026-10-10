#!/usr/bin/env python3
"""A810 AT6 measured-context tuner applied strictly after AT4 RFC1 + AT5.

Small scope, fail on drift, no shader/correctness/layout changes.
"""
from pathlib import Path
import hashlib, shutil
ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
def hashes():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in ROOT.rglob("*") if p.is_file()}
before=hashes()
def edit(path,old,new,label):
    s=path.read_text()
    n=s.count(old)
    if n!=1:raise SystemExit(f"AT6 drift/collision {label}: {n}")
    path.write_text(s.replace(old,new,1))
    print("AT6 PASS",label,flush=True)

shutil.copyfile("patches/frane_a810_at6.h",V/"frane_a810_at6.h")
auto=V/"tu_autotune.cc"
edit(auto,
     '#include "frane_a810_at5.h"',
     '#include "frane_a810_at5.h"\n#include "frane_a810_at6.h"',
     "AT6 selector header")
edit(auto,
     """static bool
frane_a810_at5_enabled(const struct tu_device *device)
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT5", true);
   return enabled && frane_a810_s1at4_enabled(device);
}""",
     """static bool
frane_a810_at5_enabled(const struct tu_device *device)
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT5", true);
   return enabled && frane_a810_s1at4_enabled(device);
}

/* Independent AT6 switch: default enabled on actual A810 only.
 * TU_FRANE_AT6=0 restores AT5 with unchanged opt-in CSV.
 */
static bool
frane_a810_at6_enabled(const struct tu_device *device)
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT6", true);
   return enabled && frane_a810_at5_enabled(device);
}""",
     "separate AT6 rollback gate")

edit(auto,
     """         bool s1at5_context = false,
         bool *at5_applied = nullptr)""",
     """         bool s1at5_context = false,
         bool *at5_applied = nullptr,
         bool s1at6_context = false,
         bool *at6_applied = nullptr)""",
     "extra selector reporting only")

edit(auto,
     """                     at1 = s1at5_context
                        ? frane_at5_decide(at1_in, snapshot, decision_word, baseline)
                        : baseline;
                     if (at5_applied && s1at5_context &&""",
     """                     const auto at5_choice = s1at5_context
                        ? frane_at5_decide(at1_in, snapshot, decision_word, baseline)
                        : baseline;
                     at1 = s1at6_context
                        ? frane_at6_decide(at1_in, snapshot, decision_word,
                                           baseline, at5_choice)
                        : at5_choice;
                     if (at6_applied && s1at6_context &&
                         at1.override_mode &&
                         (!at5_choice.override_mode ||
                          at1.select_sysmem != at5_choice.select_sysmem ||
                          at1.force_measure != at5_choice.force_measure))
                        *at6_applied = true;
                     if (at5_applied && s1at5_context &&""",
     "AT6 chooses only after AT5 and AT4, preserves their probes")

edit(auto,
     """      const bool at5 = frane_a810_at5_enabled(device);
      const bool context_eligible = !at4 ||""",
     """      const bool at5 = frane_a810_at5_enabled(device);
      const bool at6 = frane_a810_at6_enabled(device);
      const bool context_eligible = !at4 ||""",
     "scope AT6 to exactly A810 AT4 eligibility")

edit(auto,
     """      bool at5_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     """      bool at5_applied = false;
      bool at6_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     "report AT6 vs AT5")

edit(auto,
     """         at5 && context_eligible, &at5_applied);""",
     """         at5 && context_eligible, &at5_applied,
         at6 && context_eligible, &at6_applied);""",
     "pass true runtime AT6 gate")

edit(auto,
     """            depth_overrode ? "DEPTH_FRONTIER" :
            at5_applied ? "AT5_ADAPT" :""",
     """            depth_overrode ? "DEPTH_FRONTIER" :
            at6_applied ? "AT6_CALIBRATED" :
            at5_applied ? "AT5_ADAPT" :""",
     "differentiate AT6 decisions from existing AT5 CSV")

edit(V/"tu_device.cc",
     "Drnas-Turnip A810 AT5 Context Learner / Mesa ",
     "Drnas-Turnip A810 AT6 Calibrated Learner / Mesa ",
     "visible AT6 identification")

s=auto.read_text()
for token in ('debug_get_bool_option("TU_FRANE_AT6", true)',
              "frane_at6_decide(", "at6_applied ? \"AT6_CALIBRATED\"",
              "frane_a810_rfc1_timing(", "frane_a810_gmem_pass_safe("):
    assert token in s,token
assert "TU_FRANE_A810_RFC1_TRACE_PATH" in (V/"frane_a810_at4_rfc1.h").read_text()
after=hashes()
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={"vulkan/frane_a810_at6.h","vulkan/tu_autotune.cc","vulkan/tu_device.cc"}
if changed!=expected:raise SystemExit(f"AT6 unexpected edits {sorted(changed ^ expected)}")
print("AT6 measured-context runtime and independent CSV/AT5 rollback PASS",flush=True)
