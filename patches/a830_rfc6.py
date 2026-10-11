#!/usr/bin/env python3
"""A830 RFC6: reject uncertain/stale GEM/SYSMEM priors and adapt probes.
RFC5=existing behavior when TU_FRANE_A830_RFC6=0 in the same ARM64 driver.
"""
from pathlib import Path
import hashlib,shutil
ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*") if p.is_file()}
def edit(p,old,new,label):
    s=p.read_text();n=s.count(old)
    if n!=1:raise SystemExit(f"RFC6 source drift {label}: {n} anchors")
    p.write_text(s.replace(old,new,1))
    print("RFC6 PASS",label,flush=True)

shutil.copyfile("patches/frane_a830_rfc6.h",V/"frane_a830_rfc6.h")
auto=V/"tu_autotune.cc"
smart=V/"frane_mesa_26318_a810_smart_gmem.h"
edit(auto,'#include "frane_a830_rfc5.h"',
     '#include "frane_a830_rfc5.h"\n#include "frane_a830_rfc6.h"',
     "confidence helper include")
edit(smart,"   bool a830_rfc5 = false;",
     "   bool a830_rfc5 = false;\n   bool a830_rfc6 = false;",
     "RFC6 exact device metadata")

edit(auto,
     """static bool
frane_a830_rfc5_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC5", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     """static bool
frane_a830_rfc5_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC5", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_rfc6_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC6", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     "RFC6 env flag exact A830")
edit(auto,
     """         runtime_input.a830_rfc5 =
            runtime_input.a830_rfc4 && frane_a830_rfc5_enabled(device);

         if (runtime_input.a830_bw2) {""",
     """         runtime_input.a830_rfc5 =
            runtime_input.a830_rfc4 && frane_a830_rfc5_enabled(device);
         runtime_input.a830_rfc6 =
            runtime_input.a830_rfc5 && frane_a830_rfc6_enabled(device);

         if (runtime_input.a830_bw2) {""",
     "RFC6 strictly layered over existing valid RFC5")

edit(auto,
     "   std::atomic<uint32_t> frane_a830_rfc4_vol_word { 0 };",
     """   std::atomic<uint32_t> frane_a830_rfc4_vol_word { 0 };
   /* Completed GPU timestamp sample ages by rendering mode. Update only
    * from the existing submit result thread, never from command recording.
    */
   std::atomic<uint32_t> frane_a830_rfc6_last_sys { 0 };
   std::atomic<uint32_t> frane_a830_rfc6_last_gmem { 0 };""",
     "per-RP two last completed timestamp occurrences")

edit(auto,
     """         if (entry.frane_smart_sample &&
             frane_a830_rfc4_enabled(at.device)) {
            /* Use pre-update EMA to detect real scene changes, not the""",
     """         if (entry.frane_smart_sample &&
             frane_a830_rfc4_enabled(at.device)) {
            if (frane_a830_rfc6_enabled(at.device) &&
                entry.frane_smart_occurrence) {
               auto &last = entry.sysmem ? frane_a830_rfc6_last_sys
                                         : frane_a830_rfc6_last_gmem;
               last.store(entry.frane_smart_occurrence,
                          std::memory_order_relaxed);
            }
            /* Use pre-update EMA to detect real scene changes, not the""",
     "mark freshness only after actual GPU timestamp completion")

edit(auto,
     """            if (gmem_runtime_input->a830_rfc3 &&
                gmem_runtime_input->a830_rfc4 &&
                gmem_runtime_input->a830_rfc5) {
               /* RFC5: measured cost *and* confidence control exploration.""",
     """            if (gmem_runtime_input->a830_rfc6) {
               const auto trusted = frane_a830_rfc6_select(
                  true, gmem_runtime_input->a830_history_ready,
                  gmem_runtime_input->a830_history_score,
                  gmem_runtime_input->a830_history_pairs,
                  history.sysmem_rp_average.count,
                  history.gmem_rp_average.count,
                  history.sysmem_rp_average.get(),
                  history.gmem_rp_average.get(),
                  history.frane_a830_rfc4_vol_word.load(
                     std::memory_order_relaxed),
                  occurrence, history.hash,
                  history.frane_a830_rfc6_last_sys.load(
                     std::memory_order_relaxed),
                  history.frane_a830_rfc6_last_gmem.load(
                     std::memory_order_relaxed));
               /* Uncertain or stale evidence is explicitly handed back to
                * original SMART_V2 rather than forced on a weak prior.
                */
               if (trusted.accepted) {
                  *measure = trusted.base.d.measure;
                  if (rfc2_reason)
                     *rfc2_reason = trusted.base.d.audit
                        ? FRANE_A830_RFC2_RFC6_AUDIT
                        : trusted.high_confidence
                           ? FRANE_A830_RFC2_RFC6_CONFIDENT
                           : FRANE_A830_RFC2_RFC6_LEARNED;
                  return trusted.base.d.sysmem ? render_mode::SYSMEM
                                               : render_mode::GMEM;
               }
            } else if (gmem_runtime_input->a830_rfc3 &&
                gmem_runtime_input->a830_rfc4 &&
                gmem_runtime_input->a830_rfc5) {
               /* RFC5: measured cost *and* confidence control exploration.""",
     "confidence first, exact RFC5 fallback when disabled")

r=V/"frane_a830_rfc2.h"
edit(r,"   FRANE_A830_RFC2_RFC5_AUDIT = 12,",
     """   FRANE_A830_RFC2_RFC5_AUDIT = 12,
   FRANE_A830_RFC2_RFC6_LEARNED = 13,
   FRANE_A830_RFC2_RFC6_CONFIDENT = 14,
   FRANE_A830_RFC2_RFC6_AUDIT = 15,""",
     "RFC6 provenance values")
edit(r,'   case FRANE_A830_RFC2_RFC5_AUDIT: return "RFC5_AUDIT";',
     """   case FRANE_A830_RFC2_RFC5_AUDIT: return "RFC5_AUDIT";
   case FRANE_A830_RFC2_RFC6_LEARNED: return "RFC6_LEARNED";
   case FRANE_A830_RFC2_RFC6_CONFIDENT: return "RFC6_CONFIDENT";
   case FRANE_A830_RFC2_RFC6_AUDIT: return "RFC6_AUDIT";""",
     "distinguish trusted/strong/audited choices in optional CSV")
edit(V/"tu_device.cc",
     "Turnip-Drnas A830 S2-RFC5 Hotspot Learning / Mesa ",
     "Turnip-Drnas A830 S2-RFC6 Confidence Learning / Mesa ",
     "new driver identity")
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in ROOT.rglob("*") if p.is_file()}
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={"vulkan/frane_a830_rfc6.h",
          "vulkan/frane_mesa_26318_a810_smart_gmem.h",
          "vulkan/tu_autotune.cc","vulkan/frane_a830_rfc2.h","vulkan/tu_device.cc"}
assert changed==expected,("RFC6 scope",changed^expected)
print("RFC6 PASS decision ordering, measured timestamps, A/B rollback and source scope",flush=True)
