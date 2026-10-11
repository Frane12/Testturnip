#!/usr/bin/env python3
"""ATUltimate Dynamic V2 overlay: apply AFTER a810_atultimate_overlay.py.
Dynamic GPU champions are per existing AT3 context. Phase/winner hysteresis
uses a single RP-local packed atomic. AT4 probes and final safety untouched.
"""
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
auto=V/"tu_autotune.cc"
dev=V/"tu_device.cc"
def edit(p,old,new,label):
    s=p.read_text();n=s.count(old)
    if n!=1: raise SystemExit(f"ATUltimate V2 SOURCE DRIFT {label}: {n}")
    p.write_text(s.replace(old,new,1))
    print("ATUltimate V2 PASS",label,flush=True)

edit(auto,
"""   std::atomic<uint32_t> frane_atu_occurrence { 0 };""",
"""   std::atomic<uint32_t> frane_atu_occurrence { 0 };
   /* Per-render-pass champion and phase; only 8 bytes, no heap/lock. */
   std::atomic<uint64_t> frane_atu_dynamic_word { 0 };""",
     "add per-RP 64-bit dynamic phase/champion state")
edit(auto,
"""static bool frane_a810_atu_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_ATU", true);
   return on && frane_a810_at8_enabled(d);
}""",
"""static bool frane_a810_atu_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_ATU", true);
   return on && frane_a810_at8_enabled(d);
}
static bool frane_a810_atu_dynamic_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_ATU_DYNAMIC", true);
   return on && frane_a810_atu_enabled(d);
}
static bool frane_a810_atu_fast_enabled()
{
   static const bool on = debug_get_bool_option("TU_FRANE_ATU_FAST", true);
   return on;
}
static unsigned frane_a810_atu_phase_hits()
{
   static const unsigned hits = std::clamp<unsigned>(
      debug_get_num_option("TU_FRANE_ATU_PHASE_HITS",3),2u,8u);
   return hits;
}
static unsigned frane_a810_atu_dwell()
{
   static const unsigned count = std::clamp<unsigned>(
      debug_get_num_option("TU_FRANE_ATU_DWELL",24),8u,48u);
   return count;
}""",
     "runtime flags default ON with sane hysteresis limits")
edit(auto,
"""         bool s1atu_context = false, bool *atu_prior_rejected = nullptr)""",
"""         bool s1atu_context = false, bool *atu_prior_rejected = nullptr,
         bool s1atu_dynamic = false, bool *atu_dynamic_applied = nullptr,
         frane_atu_dyn_result *atu_dynamic_diag = nullptr)""",
     "real selector receives phase learner switch and provenance")
edit(auto,
"""                  at3_sampling = at1.override_mode;""",
"""                  /* Phase-aware champion after AT4/AT7/AT63 and the
                   * AT6 prior, BEFORE existing runtime final selector.
                   * Never defeat a forced measurement or earlier override.
                   * A trusted champion uses the same GPU history snapshots.
                   */
                  if (s1atu_dynamic && s1at4_context) {
                     const auto dynamic = frane_atu_dyn_step(
                        history.frane_atu_dynamic_word,at1_in,snapshot,
                        !at1.override_mode && !runtime_decision.override_mode,
                        frane_a810_atu_fast_enabled(),
                        frane_a810_atu_phase_hits(),
                        frane_a810_atu_dwell());
                     if (atu_dynamic_diag) *atu_dynamic_diag = dynamic;
                     if (dynamic.used) {
                        at1 = dynamic.decision;
                        if (atu_dynamic_applied)
                           *atu_dynamic_applied = true;
                     }
                  }
                  at3_sampling = at1.override_mode;""",
     "single authoritative dynamic selection after prior, still preserves probes")
edit(auto,
"""      const bool atu = frane_a810_atu_enabled(device);
      const bool context_eligible = !at4 ||""",
"""      const bool atu = frane_a810_atu_enabled(device);
      const bool dynamic = frane_a810_atu_dynamic_enabled(device);
      const bool context_eligible = !at4 ||""",
     "enable dynamic on real A810 render path only")
edit(auto,
"""      bool atu_prior_rejected = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
"""      bool atu_prior_rejected = false;
      bool atu_dynamic_applied = false;
      frane_atu_dyn_result atu_dynamic_diag {};
      render_mode mode = history.profiled.get_optimal_mode(""",
     "capture category learning and dynamic provenance")
edit(auto,
"""         atu && context_eligible, &atu_prior_rejected);""",
"""         atu && context_eligible, &atu_prior_rejected,
         dynamic && context_eligible, &atu_dynamic_applied,
         &atu_dynamic_diag);""",
     "pass dynamic gate and state back from actual selector")
edit(auto,
"""            atu_prior_rejected ? "ATU_HISTORY_GUARD" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :""",
"""            atu_dynamic_applied ? "ATU_DYNAMIC_WINNER" :
            atu_prior_rejected ? "ATU_HISTORY_GUARD" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :""",
     "tag dynamic GPU champion in RFC1 trace")
edit(auto,
"""         row.prior_rejected = atu_prior_rejected;
         row.source = safety_forced ? "GMEM_SAFETY" :""",
"""         row.prior_rejected = atu_prior_rejected;
         row.dynamic = atu_dynamic_diag;
         row.source = safety_forced ? "GMEM_SAFETY" :""",
     "add dynamic learning state to existing render-context logger")
edit(auto,
"""            atu_prior_rejected ? "ATU_HISTORY_GUARD" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :""",
"""            atu_dynamic_applied ? "ATU_DYNAMIC_WINNER" :
            atu_prior_rejected ? "ATU_HISTORY_GUARD" :
            at8_applied ? "AT8_EARLY_GPU_WINNER" :""",
     "actual context logging identifies dynamic winner")
edit(dev,"Drnas-Turnip A810 ATUltimate Context Learner / Mesa ",
         "Drnas-Turnip A810 ATUltimate Dynamic V2 / Mesa ",
     "driverInfo reflects dynamic binary")
s=auto.read_text()
assert s.count("frane_atu_dyn_step(")==1
assert "TU_FRANE_ATU_DYNAMIC" in s
assert "TU_FRANE_ATU_PHASE_HITS" in s and "TU_FRANE_ATU_DWELL" in s
assert s.index("frane_atu_dyn_step(")<s.index("at3_sampling = at1.override_mode;")
assert s.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)")<s.index("frane_atu_trace(row,history.frane_s1at3_words)")
assert not any(x in s for x in ("TU_FRANE_AT9","frane_at9_fc2","AT9_FC2_PRIOR"))
print("ATUltimate V2 final Mesa selector, phase/clock hysteresis, AT4 correctness and log PASS")
