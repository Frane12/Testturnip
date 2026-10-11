#!/usr/bin/env python3
"""ATUltimate V3 overlay AFTER V2. Respect AT4 probes, move dynamic decision
before AT8/7/63, and preserve V2 as explicit runtime fallback.
Strict unique Mesa source anchors abort on drift.
"""
from pathlib import Path
import shutil
V=Path("mesa/src/freedreno/vulkan")
auto=V/"tu_autotune.cc"
dev=V/"tu_device.cc"
shutil.copyfile("patches/frane_a810_atultimate_v3.h",V/"frane_a810_atultimate_v3.h")
def edit(path,old,new,label):
    s=path.read_text()
    n=s.count(old)
    if n!=1: raise SystemExit(f"ATUltimate V3 SOURCE DRIFT {label}: {n}")
    path.write_text(s.replace(old,new,1))
    print("ATUltimate V3 PASS",label,flush=True)
edit(auto,
"""   std::atomic<uint64_t> frane_atu_dynamic_word { 0 };""",
"""   std::atomic<uint64_t> frane_atu_dynamic_word { 0 };
   /* Four bounded associative categories; no heap or GPU queries. */
   std::atomic<uint64_t> frane_atu_v3_cache[FRANE_ATU_V3_SLOTS]{};
   std::atomic<uint32_t> frane_atu_v3_epoch { 0 };""",
   "4-way RP category history and bounded sequence")
edit(auto,
"""static bool frane_a810_atu_dynamic_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_ATU_DYNAMIC", true);
   return on && frane_a810_atu_enabled(d);
}""",
"""static bool frane_a810_atu_dynamic_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_ATU_DYNAMIC", true);
   return on && frane_a810_atu_enabled(d);
}
static bool frane_a810_atu_v3_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_ATU_V3", true);
   return on && frane_a810_atu_dynamic_enabled(d);
}""",
   "V3 enabled by default; V3=0 retains V2, DYNAMIC=0 retains ATUltimate")
edit(auto,
"""         bool s1atu_dynamic = false, bool *atu_dynamic_applied = nullptr,
         frane_atu_dyn_result *atu_dynamic_diag = nullptr)""",
"""         bool s1atu_dynamic = false, bool *atu_dynamic_applied = nullptr,
         frane_atu_dyn_result *atu_dynamic_diag = nullptr,
         bool s1atu_v3_context = false, bool *atu_v3_applied = nullptr,
         frane_atu_v3_result *atu_v3_diag = nullptr)""",
   "V3 actual selector runtime parameters")
edit(auto,
"""                  if (s1at8_context && s1at7_context &&
                      s1at63_context && s1at4_context &&
                      !runtime_decision.override_mode &&
                      !at1.override_mode) {""",
"""                  /* Give V3 a chance BEFORE early AT8/AT7/AT63 winners.
                   * AT4 exploration and S1 runtime override take priority.
                   * V3 may only select the current fresh AT3 GPU winner.
                   */
                  if (s1atu_v3_context && s1at4_context) {
                     const auto v3 = frane_atu_v3_step(
                        history.frane_atu_v3_cache,
                        history.frane_atu_dynamic_word,
                        history.frane_atu_v3_epoch,
                        at1_in,snapshot,
                        !at1.override_mode && !runtime_decision.override_mode,
                        at1.force_measure,runtime_decision.override_mode,
                        frane_a810_atu_fast_enabled(),
                        frane_a810_atu_phase_hits(),frane_a810_atu_dwell());
                     if (atu_v3_diag) *atu_v3_diag = v3;
                     if (v3.used) {
                        at1 = v3.decision;
                        if (atu_v3_applied) *atu_v3_applied = true;
                     }
                  }
                  if (s1at8_context && s1at7_context &&
                      s1at63_context && s1at4_context &&
                      !runtime_decision.override_mode &&
                      !at1.override_mode) {""",
   "V3 wins before early measured selectors, never overrides AT4 measurement")
edit(auto,
"""                  if (s1atu_dynamic && s1at4_context) {""",
"""                  if (s1atu_dynamic && !s1atu_v3_context &&
                      s1at4_context) {""",
   "disable V2 selector whenever V3 active; retain V2 rollback")
edit(auto,
"""      const bool dynamic = frane_a810_atu_dynamic_enabled(device);
      const bool context_eligible = !at4 ||""",
"""      const bool dynamic = frane_a810_atu_dynamic_enabled(device);
      const bool v3 = frane_a810_atu_v3_enabled(device);
      const bool context_eligible = !at4 ||""",
   "V3 A810 feature gate on real render path")
edit(auto,
"""      frane_atu_dyn_result atu_dynamic_diag {};
      render_mode mode = history.profiled.get_optimal_mode(""",
"""      frane_atu_dyn_result atu_dynamic_diag {};
      bool atu_v3_applied = false;
      frane_atu_v3_result atu_v3_diag {};
      render_mode mode = history.profiled.get_optimal_mode(""",
   "store V3 diagnostic with no logging requirement")
edit(auto,
"""         dynamic && context_eligible, &atu_dynamic_applied,
         &atu_dynamic_diag);""",
"""         dynamic && context_eligible, &atu_dynamic_applied,
         &atu_dynamic_diag,
         v3 && context_eligible, &atu_v3_applied,
         &atu_v3_diag);""",
   "connect V3 to actual selector independent of tracing")
edit(auto,
"""            atu_dynamic_applied ? "ATU_DYNAMIC_WINNER" :
            atu_prior_rejected ? "ATU_HISTORY_GUARD" :""",
"""            atu_v3_applied ? "ATU_V3_CATEGORY_WINNER" :
            atu_dynamic_applied ? "ATU_DYNAMIC_WINNER" :
            atu_prior_rejected ? "ATU_HISTORY_GUARD" :""",
   "legacy RFC1 GPU trace provenance: dynamic V3")
edit(auto,
"""         row.dynamic = atu_dynamic_diag;
         row.source = safety_forced ? "GMEM_SAFETY" :""",
"""         row.dynamic = atu_dynamic_diag;
         row.v3 = atu_v3_diag;
         row.source = safety_forced ? "GMEM_SAFETY" :""",
   "V3 diagnostics report from actual final choice")
edit(auto,
"""            atu_dynamic_applied ? "ATU_DYNAMIC_WINNER" :
            atu_prior_rejected ? "ATU_HISTORY_GUARD" :""",
"""            atu_v3_applied ? "ATU_V3_CATEGORY_WINNER" :
            atu_dynamic_applied ? "ATU_DYNAMIC_WINNER" :
            atu_prior_rejected ? "ATU_HISTORY_GUARD" :""",
   "context logger provenance for V3")
edit(dev, "Drnas-Turnip A810 ATUltimate Dynamic V2 / Mesa ",
     "Drnas-Turnip A810 ATUltimate Dynamic V3 / Mesa ",
     "identify actual V3 binary")
s=auto.read_text()
assert s.index("frane_atu_v3_step(") < s.index("frane_at8_early_winner(")
assert s.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") < s.index("frane_atu_trace(row,history.frane_s1at3_words)")
for tok in ("TU_FRANE_ATU_V3", "frane_atu_v3_cache","frane_atu_v3_epoch","ATU_V3_CATEGORY_WINNER","!s1atu_v3_context"):
    assert tok in s,tok
assert "TU_FRANE_AT9" not in s
print("ATUltimate V3: real Mesa selector, AT4 probes, AT8 and GPU safety preserved PASS")
