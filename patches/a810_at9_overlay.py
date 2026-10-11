#!/usr/bin/env python3
"""A810 AT9 FC2 measured rescue; apply AFTER AT7, CP1, AT8.
Anchored to tested AT8 runtime. Preserve final GMEM/depth safety and AT4 probes.
"""
from pathlib import Path
import shutil
V=Path("mesa/src/freedreno/vulkan")
auto=V/"tu_autotune.cc"
dev=V/"tu_device.cc"
def edit(path,old,new,name):
    s=path.read_text()
    n=s.count(old)
    if n != 1:
        raise SystemExit(f"AT9 SOURCE DRIFT {name}: {n}")
    path.write_text(s.replace(old,new,1))
    print("AT9 PASS",name,flush=True)

shutil.copyfile("patches/frane_a810_at9_fc2.h",V/"frane_a810_at9_fc2.h")
edit(auto, '#include "frane_a810_at8_early.h"',
     '#include "frane_a810_at8_early.h"\n#include "frane_a810_at9_fc2.h"',
     "include AT9 FC2 GPU-time policy")
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
static bool frane_a810_at9_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT9", true);
   return on && frane_a810_at8_enabled(d);
}""", "explicit A810-only AT9 gate default ON, revertible")
edit(auto,
"""         bool s1at8_context = false, bool *at8_applied = nullptr)""",
"""         bool s1at8_context = false, bool *at8_applied = nullptr,
         bool s1at9_context = false, bool *at9_rescue = nullptr,
         bool *at9_prior = nullptr)""","AT9 selector params default off for older callers")
edit(auto,
"""                  if (s1at8_context && s1at7_context &&
                      s1at63_context && s1at4_context &&""",
"""                  /* Rescue FC2-like expensive passes with timestamp
                   * winner even when a legacy heuristic already chose.
                   * Never swallow AT4 or runtime forced measurements. */
                  if (s1at9_context && s1at8_context &&
                      s1at4_context) {
                     const auto rescue = frane_at9_fc2_measured(
                        at1_in, snapshot, decision_word, at1,
                        runtime_decision.force_measure);
                     if (rescue.override_mode) {
                        at1 = rescue;
                        if (at9_rescue) *at9_rescue = true;
                     }
                  }
                  if (s1at8_context && s1at7_context &&
                      s1at63_context && s1at4_context &&""",
     "GPU-observed winner before AT8/AT7/AT63, preserving forced probes")
edit(auto,
"""                  if (s1at6_context && s1at4_context &&
                      !at1.override_mode && !runtime_decision.override_mode) {""",
"""                  /* The FC2 trace favors SYS on high-draw 522240px
                   * load/store-asymmetric passes, but not universally.
                   * Prior expires once 3 paired GPU timings exist.
                   * Existing AT6 fallback stays unmodified. */
                  if (s1at9_context && s1at4_context &&
                      !at1.override_mode && !runtime_decision.override_mode) {
                     const auto prior = frane_at9_fc2_prior(
                        at1_in, snapshot, decision_word, at1);
                     if (prior.override_mode) {
                        at1 = prior;
                        if (at9_prior) *at9_prior = true;
                     }
                  }
                  if (s1at6_context && s1at4_context &&
                      !at1.override_mode && !runtime_decision.override_mode) {""",
     "measured priority then bounded reversible FC2 prior")
edit(auto,
"""      const bool at8 = frane_a810_at8_enabled(device);
      const bool context_eligible = !at4 ||""",
"""      const bool at8 = frane_a810_at8_enabled(device);
      const bool at9 = frane_a810_at9_enabled(device);
      const bool context_eligible = !at4 ||""",
     "A810 AT9 gate is active on actual render path")
edit(auto,
"""      bool at8_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
"""      bool at8_applied = false;
      bool at9_rescue = false;
      bool at9_prior = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     "AT9 provenance counters in call site")
edit(auto,
"""         at8 && context_eligible, &at8_applied);""",
"""         at8 && context_eligible, &at8_applied,
         at9 && context_eligible, &at9_rescue, &at9_prior);""",
     "forward AT9 mode decisions to real autotuner")
edit(auto,
"""            at8_applied ? "AT8_EARLY_GPU_WINNER" :""",
"""            at9_rescue ? "AT9_FC2_GPU_RESCUE" :
            at9_prior ? "AT9_FC2_PRIOR" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :""",
     "source-tag AT9 in existing opt-in GPU CSV")
edit(dev,"Drnas-Turnip A810 AT8 Early GPU Winner / Mesa ",
         "Drnas-Turnip A810 AT9 FC2 Measured Rescue / Mesa ",
     "unique driver version")
s=auto.read_text()
for token in ("TU_FRANE_AT9","frane_at9_fc2_measured(","frane_at9_fc2_prior(",
              "at9 && context_eligible","AT9_FC2_GPU_RESCUE","AT9_FC2_PRIOR",
              "frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)",
              "frane_a810_rfc1_decision("):
    assert token in s,token
assert s.index("frane_at9_fc2_measured(") < s.index("frane_at8_early_winner(")
assert s.index("frane_at9_fc2_prior(") < s.index("frane_at63_prior(")
assert s.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") < s.index("frane_a810_rfc1_decision(")
assert "TU_FRANE_AT5" not in s
print("AT9 A810 actual selector, prior, rollback and post-safety GPU logging PASS",flush=True)
