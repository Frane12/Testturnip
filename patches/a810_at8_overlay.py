#!/usr/bin/env python3
"""AT8 add-on applied AFTER A810 AT7 + CP1. Strict source anchors.
 Only changes measured winner selection at two paired samples.
"""
from pathlib import Path
import shutil
V = Path("mesa/src/freedreno/vulkan")
auto = V / "tu_autotune.cc"
dev = V / "tu_device.cc"

def edit(path, old, new, label):
    s = path.read_text()
    matches = s.count(old)
    if matches != 1:
        raise SystemExit(f"AT8 SOURCE DRIFT {label}: {matches}")
    path.write_text(s.replace(old, new, 1))
    print("AT8 PASS", label, flush=True)

shutil.copyfile("patches/frane_a810_at8_early.h", V / "frane_a810_at8_early.h")
edit(auto, '#include "frane_a810_at7_utility.h"',
     '#include "frane_a810_at7_utility.h"\n#include "frane_a810_at8_early.h"',
     "AT8 GPU-measured two-pair policy include")
edit(auto,
"""static bool frane_a810_at7_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT7", true);
   return on && frane_a810_at63_enabled(d);
}""",
"""static bool frane_a810_at7_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT7", true);
   return on && frane_a810_at63_enabled(d);
}
static bool frane_a810_at8_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT8", true);
   return on && frane_a810_at7_enabled(d);
}""", "AT8 runtime toggle with exact AT7 rollback")
edit(auto,
"""         bool s1at7_context = false, bool *at7_applied = nullptr)""",
"""         bool s1at7_context = false, bool *at7_applied = nullptr,
         bool s1at8_context = false, bool *at8_applied = nullptr)""",
     "AT8 selector context and instrumentation")
edit(auto,
"""                  if (s1at7_context && s1at63_context &&
                      s1at4_context && !runtime_decision.override_mode) {""",
"""                  if (s1at8_context && s1at7_context &&
                      s1at63_context && s1at4_context &&
                      !runtime_decision.override_mode &&
                      !at1.override_mode) {
                     const auto very_early = frane_at8_early_winner(
                        at1_in, snapshot, decision_word, at1);
                     if (very_early.override_mode) {
                        at1 = very_early;
                        if (at8_applied) *at8_applied = true;
                     }
                  }
                  if (s1at7_context && s1at63_context &&
                      s1at4_context && !runtime_decision.override_mode) {""",
     "AT8 winner before AT7/AT63, with existing render safety")
edit(auto,
"""      const bool at7 = frane_a810_at7_enabled(device);
      const bool context_eligible = !at4 ||""",
"""      const bool at7 = frane_a810_at7_enabled(device);
      const bool at8 = frane_a810_at8_enabled(device);
      const bool context_eligible = !at4 ||""",
     "A810-only feature gate at runtime call site")
edit(auto,
"""      bool at7_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
"""      bool at7_applied = false;
      bool at8_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     "AT8 decision provenance before final safety")
edit(auto,
"""         at7 && context_eligible, &at7_applied);""",
"""         at7 && context_eligible, &at7_applied,
         at8 && context_eligible, &at8_applied);""",
     "pass AT8 selector gate and provenance")
edit(auto,
"""            at7_applied ? "AT7_UTILITY_WINNER" :""",
"""            at8_applied ? "AT8_EARLY_GPU_WINNER" :
            at7_applied ? "AT7_UTILITY_WINNER" :""",
     "optional RFC1 CSV reports AT8 source")
edit(dev, "Drnas-Turnip A810 AT7 Utility Winner / Mesa ",
          "Drnas-Turnip A810 AT8 Early GPU Winner / Mesa ",
     "unique Vulkan driverInfo for identifying binary")

s = auto.read_text()
for required in ("TU_FRANE_AT8", "frane_at8_early_winner(",
                 "AT8_EARLY_GPU_WINNER", "at8 && context_eligible",
                 "frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)",
                 "frane_a810_rfc1_decision("):
    assert required in s, required
assert s.index("frane_at8_early_winner(") < s.index("frane_at7_utility_winner(")
assert s.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") < s.index("frane_a810_rfc1_decision(")
assert "TU_FRANE_AT5" not in s
print("AT8 final runtime A810/AT7/AT63/AT4/safety/log pipeline PASS", flush=True)
