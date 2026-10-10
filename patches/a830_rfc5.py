#!/usr/bin/env python3
"""RFC5 after tested RFC4: cost-aware measured learner with same-code A/B.
No GPU queries, no renderpass layout changes, only measured mode policy.
"""
from pathlib import Path
import hashlib, shutil
ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*") if p.is_file()}
def edit(p,o,n,label):
    s=p.read_text()
    k=s.count(o)
    if k!=1: raise SystemExit(f"RFC5 anchor drift: {label} occurrences={k}")
    p.write_text(s.replace(o,n,1))
    print("RFC5 PASS",label,flush=True)

shutil.copyfile("patches/frane_a830_rfc5.h", V/"frane_a830_rfc5.h")
auto=V/"tu_autotune.cc"
smart=V/"frane_mesa_26318_a810_smart_gmem.h"
edit(auto,
     '#include "frane_a830_rfc4.h"',
     '#include "frane_a830_rfc4.h"\n#include "frane_a830_rfc5.h"',
     "include cost-aware learner")
edit(smart,
     "   bool a830_rfc4 = false;",
     "   bool a830_rfc4 = false;\n   bool a830_rfc5 = false;",
     "exact device SMART metadata")

edit(auto,
     """static bool
frane_a830_rfc4_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC4", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     """static bool
frane_a830_rfc4_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC4", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_rfc5_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC5", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     "RFC5 A/B flag on exact A830")

edit(auto,
     """         runtime_input.a830_rfc4 =
            runtime_input.a830_rfc3 && frane_a830_rfc4_enabled(device);

         if (runtime_input.a830_bw2) {""",
     """         runtime_input.a830_rfc4 =
            runtime_input.a830_rfc3 && frane_a830_rfc4_enabled(device);
         runtime_input.a830_rfc5 =
            runtime_input.a830_rfc4 && frane_a830_rfc5_enabled(device);

         if (runtime_input.a830_bw2) {""",
     "RFC5 only when RFC4+RFC3 remain enabled")

edit(auto,
     """            if (gmem_runtime_input->a830_rfc3 &&
                gmem_runtime_input->a830_rfc4) {
               const auto learned = frane_a830_rfc4_select(""",
     """            if (gmem_runtime_input->a830_rfc3 &&
                gmem_runtime_input->a830_rfc4 &&
                gmem_runtime_input->a830_rfc5) {
               /* RFC5: measured cost *and* confidence control exploration.
                * RFC4 selection is retained unchanged for non-targets.
                */
               const auto hot = frane_a830_rfc5_select(
                  true, gmem_runtime_input->a830_history_ready,
                  gmem_runtime_input->a830_history_score,
                  gmem_runtime_input->a830_history_pairs,
                  history.sysmem_rp_average.count,
                  history.gmem_rp_average.count,
                  history.sysmem_rp_average.get(),
                  history.gmem_rp_average.get(),
                  history.frane_a830_rfc4_vol_word.load(
                     std::memory_order_relaxed),
                  occurrence, history.hash);
               if (hot.d.owns) {
                  *measure = hot.d.measure;
                  if (rfc2_reason)
                     *rfc2_reason = hot.d.audit
                        ? FRANE_A830_RFC2_RFC5_AUDIT
                        : hot.workload_class == FRANE_A830_RFC5_HOT_CLOSE
                           ? FRANE_A830_RFC2_RFC5_HOT
                           : hot.workload_class == FRANE_A830_RFC5_TINY_STABLE
                              ? FRANE_A830_RFC2_RFC5_TINY
                              : FRANE_A830_RFC2_REGIME_LEARNED;
                  return hot.d.sysmem ? render_mode::SYSMEM
                                      : render_mode::GMEM;
               }
            } else if (gmem_runtime_input->a830_rfc3 &&
                gmem_runtime_input->a830_rfc4) {
               const auto learned = frane_a830_rfc4_select(""",
     "RFC5 before RFC4 same-driver fallback, still before SMART_V2")

r=V/"frane_a830_rfc2.h"
edit(r,
     "   FRANE_A830_RFC2_REGIME_LEARNED = 9,",
     """   FRANE_A830_RFC2_REGIME_LEARNED = 9,
   FRANE_A830_RFC2_RFC5_HOT = 10,
   FRANE_A830_RFC2_RFC5_TINY = 11,
   FRANE_A830_RFC2_RFC5_AUDIT = 12,""",
     "source provenance for cost-aware decisions")
edit(r,
     """   case FRANE_A830_RFC2_REGIME_LEARNED: return "REGIME_LEARNED";""",
     """   case FRANE_A830_RFC2_REGIME_LEARNED: return "REGIME_LEARNED";
   case FRANE_A830_RFC2_RFC5_HOT: return "RFC5_HOT";
   case FRANE_A830_RFC2_RFC5_TINY: return "RFC5_TINY";
   case FRANE_A830_RFC2_RFC5_AUDIT: return "RFC5_AUDIT";""",
     "log new decision types")
edit(r,"if (budget.fetch_add(1, std::memory_order_relaxed) >= 8192u)",
     "if (budget.fetch_add(1, std::memory_order_relaxed) >= 16384u)",
     "larger evidence window; only when CSV logging enabled")

edit(V/"tu_device.cc",
     "Turnip-Drnas A830 S2-RFC4 Adaptive Learning / Mesa ",
     "Turnip-Drnas A830 S2-RFC5 Hotspot Learning / Mesa ",
     "new driver identity")

after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in ROOT.rglob("*") if p.is_file()}
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={"vulkan/frane_a830_rfc5.h",
          "vulkan/frane_mesa_26318_a810_smart_gmem.h",
          "vulkan/tu_autotune.cc","vulkan/frane_a830_rfc2.h",
          "vulkan/tu_device.cc"}
assert changed==expected,(changed^expected)
print("RFC5 PASS exclusive runtime scope and A/B fallback",flush=True)
