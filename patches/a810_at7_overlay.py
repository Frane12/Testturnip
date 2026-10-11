#!/usr/bin/env python3
"""Apply A810 AT6.3 reconstruction + conservative AT7 overlay to pinned AT4+RFC1.
 Guard every selector anchor. Do not touch shaders, tiling, LRZ or GPU queries.
"""
from pathlib import Path
import shutil
V=Path("mesa/src/freedreno/vulkan")
def edit(p, old, new, label):
    s=p.read_text()
    n=s.count(old)
    if n != 1: raise SystemExit(f"AT7 SOURCE DRIFT {label}: {n}")
    p.write_text(s.replace(old,new,1))
    print("AT7 PASS",label,flush=True)
for name in ["frane_a810_at6_at4base.h",
             "frane_a810_at63_earlywinner.h","frane_a810_at7_utility.h"]:
    shutil.copyfile("patches/"+name,V/name)
auto=V/"tu_autotune.cc"
history=V/"frane_s1at3_fast.h"
rfc=V/"frane_a810_at4_rfc1.h"

# Low 40 bits remain IDENTICAL to AT6.3 (tag, score, volatility, samples, stale).
# In unused 64-bit snapshot bits: 40..51 conservative saving/4us, 52..59 MAD noise.
edit(history, """   bool stale[2] {};
};""",
"""   bool stale[2] {};
   uint16_t at7_saving_4us = 0;
   uint8_t at7_noise_q8 = 255;
};""", "extend existing atomic snapshot without new tables")
edit(history, """   return uint64_t(s.signature) |
      (uint64_t(std::clamp<int>(s.score, -31, 31) + 32) << 16) |""",
"""   uint64_t lower_bound_ticks = 0;
   uint32_t noise_q8 = 255;
   if (s.mode[0].samples >= 2 && s.mode[1].samples >= 2) {
      const uint64_t sys = s.mode[0].mean;
      const uint64_t gm = s.mode[1].mean;
      const uint64_t diff = sys > gm ? sys - gm : gm - sys;
      const uint64_t uncertainty = s.mode[0].mad / 2 + s.mode[1].mad / 2;
      /* Do not count contradictory direction as a confident saved time. */
      const bool sign_consistent =
         (s.score > 0 && sys > gm) || (s.score < 0 && gm > sys);
      if (sign_consistent && diff > uncertainty)
         lower_bound_ticks = diff - uncertainty;
      noise_q8 = std::min<uint32_t>(255,
         frane_s1at1_ratio_q8(s.mode[0].mad + s.mode[1].mad,
                              std::max<uint64_t>(1,sys + gm)));
   }
   /* 19.2 MHz counter: 4 microseconds ~= 76.8 ticks, round DOWN
    * using 77 ticks per bucket, never exaggerate expected saving.
    */
   const uint64_t saving_q4us = std::min<uint64_t>(4095,lower_bound_ticks / 77u);
   return (saving_q4us << 40) | (uint64_t(noise_q8) << 52) |
      uint64_t(s.signature) |
      (uint64_t(std::clamp<int>(s.score, -31, 31) + 32) << 16) |""","compute conservative absolute GPU-time saving on submit thread")
edit(history, """   s.stale[1] = (word >> 39) & 1;
   return s;""",
"""   s.stale[1] = (word >> 39) & 1;
   s.at7_saving_4us = uint16_t((word >> 40) & 4095u);
   s.at7_noise_q8 = uint8_t((word >> 52) & 255u);
   return s;""","read existing atomic packed duration benefit")

# Preserve AT6.3 source selection; add utility winner BEFORE >=4 pair AT63.
edit(auto, '#include "frane_a810_at4_rfc1.h"',
     '#include "frane_a810_at4_rfc1.h"\n#include "frane_a810_at7_utility.h"',
     "AT7 policy header and AT6/AT63 includes")

edit(auto, """static bool
frane_a810_s1at4_enabled(const struct tu_device *device)
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT4", true);
   return enabled && frane_a810_s1at3_enabled(device);
}""",
"""static bool
frane_a810_s1at4_enabled(const struct tu_device *device)
{
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT4", true);
   return enabled && frane_a810_s1at3_enabled(device);
}
/* AT6.3 independent of AT5; all modes retain exact A810 and AT4 gates. */
static bool frane_a810_at6_at4base_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT6", true);
   return on && frane_a810_s1at4_enabled(d);
}
static bool frane_a810_at63_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT63", true);
   return on && frane_a810_at6_at4base_enabled(d);
}
static bool frane_a810_at7_enabled(const struct tu_device *d)
{
   static const bool on = debug_get_bool_option("TU_FRANE_AT7", true);
   return on && frane_a810_at63_enabled(d);
}""","separate rollback gates for AT4 AT63 AT7")

edit(auto, """         bool *at3_controlled = nullptr,
         bool *at4_applied = nullptr)""",
"""         bool *at3_controlled = nullptr,
         bool *at4_applied = nullptr,
         bool s1at6_context = false, bool *at6_applied = nullptr,
         bool s1at63_context = false, bool *at63_applied = nullptr,
         bool s1at7_context = false, bool *at7_applied = nullptr)""",
     "selector owns opt-in utility gate")
edit(auto, """                  at1 = s1at4_context ?
                     frane_at4_decide(at1_in, snapshot, decision_word) :
                     frane_s1at3_decide(at1_in, snapshot, decision_word);
                  at3_sampling = at1.override_mode;""",
"""                  at1 = s1at4_context ?
                     frane_at4_decide(at1_in, snapshot, decision_word) :
                     frane_s1at3_decide(at1_in, snapshot, decision_word);
                  if (s1at7_context && s1at63_context &&
                      s1at4_context && !runtime_decision.override_mode) {
                     const auto utility = frane_at7_utility_winner(
                        at1_in, snapshot, decision_word, at1);
                     if (utility.override_mode) {
                        at1 = utility;
                        if (at7_applied) *at7_applied = true;
                     }
                  }
                  if (s1at63_context && s1at6_context && s1at4_context &&
                      !at1.override_mode && !runtime_decision.override_mode) {
                     const auto early = frane_at63_measured_winner(
                        at1_in, snapshot, decision_word, at1);
                     if (early.override_mode) {
                        at1 = early;
                        if (at63_applied) *at63_applied = true;
                     }
                  }
                  if (s1at6_context && s1at4_context &&
                      !at1.override_mode && !runtime_decision.override_mode) {
                     const auto prior = s1at63_context ?
                        frane_at63_prior(at1_in, snapshot, decision_word, at1) :
                        frane_at6_at4base_prior(at1_in, snapshot, decision_word, at1);
                     if (prior.override_mode) {
                        if (at6_applied) *at6_applied = true;
                        select_sysmem = prior.select_sysmem;
                     }
                  }
                  at3_sampling = at1.override_mode;""",
     "actual AT7 and AT63 selection before AT6 fallback")

edit(auto, """      const bool at4 = frane_a810_s1at4_enabled(device);
      const bool context_eligible = !at4 ||""",
"""      const bool at4 = frane_a810_s1at4_enabled(device);
      const bool at6 = frane_a810_at6_at4base_enabled(device);
      const bool at63 = frane_a810_at63_enabled(device);
      const bool at7 = frane_a810_at7_enabled(device);
      const bool context_eligible = !at4 ||""",
     "A810-specific call-site gate")
edit(auto, """      bool at4_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
"""      bool at4_applied = false;
      bool at6_applied = false;
      bool at63_applied = false;
      bool at7_applied = false;
      render_mode mode = history.profiled.get_optimal_mode(""",
     "selector decision attribution flags")
edit(auto, """         at4 && context_eligible, &at3_controlled, &at4_applied);""",
"""         at4 && context_eligible, &at3_controlled, &at4_applied,
         at6 && context_eligible, &at6_applied,
         at63 && context_eligible, &at63_applied,
         at7 && context_eligible, &at7_applied);""",
     "A810 protected runtime selector argument flow")
edit(auto, """            depth_overrode ? "DEPTH_FRONTIER" :
            at4_applied ? "AT4_OVERRIDE" :""",
"""            depth_overrode ? "DEPTH_FRONTIER" :
            at7_applied ? "AT7_UTILITY_WINNER" :
            at63_applied ? "AT63_EARLY_WINNER" :
            at6_applied ? "AT6_AT4BASE" :
            at4_applied ? "AT4_OVERRIDE" :""",
     "post-safety CSV provenance for AT7 and AT63")
edit(V/"tu_device.cc","Drnas-Turnip A810 AT4-RFC1 Trace / Mesa ",
     "Drnas-Turnip A810 AT7 Utility Winner / Mesa ","unique driverInfo")

# Correct raw 19.2MHz timestamp labels in optional v2 CSV, never in policy.
edit(rfc, "static inline const char *\nfrane_a810_rfc1_path()",
"""static inline uint64_t frane_a810_rfc1_ticks_to_ns(uint64_t ticks) {
   const __uint128_t ns = __uint128_t(ticks) * 625u / 12u;
   return ns > UINT64_MAX ? UINT64_MAX : uint64_t(ns);
}
static inline const char *
frane_a810_rfc1_path()""",
     "GPU timestamp unit conversion only in optional CSV")
edit(auto,
"""               entry.frane_s1at1_signature, entry.sysmem, rp_duration,
               sysmem_rp_average.get(), gmem_rp_average.get(),""",
"""               entry.frane_s1at1_signature, entry.sysmem,
               frane_a810_rfc1_ticks_to_ns(rp_duration),
               frane_a810_rfc1_ticks_to_ns(sysmem_rp_average.get()),
               frane_a810_rfc1_ticks_to_ns(gmem_rp_average.get()),""",
     "CSV v2 nanoseconds, same learning tick inputs")
assert "TU_FRANE_AT5" not in auto.read_text()
assert "frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)" in auto.read_text()
print("AT7 runtime reconstructed from AT6.3 source with no AT5, preserving safety")
