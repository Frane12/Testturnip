#!/usr/bin/env python3
"""RFC4: measured bidirectional adaptive control + compact volatility feedback.
RFC3 remains available unmodified via TU_FRANE_A830_RFC4=0.
Append-compatible? No: RFC4 writes a new CSV schema/path with session id.
"""
from pathlib import Path
import hashlib,shutil
ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*") if p.is_file()}

def edit(path,old,new,name):
    content=path.read_text()
    count=content.count(old)
    if count!=1:
        raise SystemExit(f"RFC4 anchor collision {name}: matches={count}")
    path.write_text(content.replace(old,new,1))
    print("RFC4 PASS",name,flush=True)

shutil.copyfile("patches/frane_a830_rfc4.h",V/"frane_a830_rfc4.h")
smart=V/"frane_mesa_26318_a810_smart_gmem.h"
edit(smart,"   bool a830_rfc3 = false;",
     "   bool a830_rfc3 = false;\n   bool a830_rfc4 = false;",
     "extend exact-A830 SMART input for bidirectional mode")
auto=V/"tu_autotune.cc"
edit(auto,
     '#include "frane_a830_rfc3.h"',
     '#include "frane_a830_rfc3.h"\n#include "frane_a830_rfc4.h"',
     "include RFC4 helper")

edit(auto,
     """static bool
frane_a830_rfc3_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC3_GUARD", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     """static bool
frane_a830_rfc3_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC3_GUARD", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_rfc4_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_RFC4", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     "A830-specific RFC4 switch")

edit(auto,
     """         runtime_input.a830_rfc3 =
            runtime_input.a830_rfc1 && frane_a830_rfc3_enabled(device);

         if (runtime_input.a830_bw2) {""",
     """         runtime_input.a830_rfc3 =
            runtime_input.a830_rfc1 && frane_a830_rfc3_enabled(device);
         runtime_input.a830_rfc4 =
            runtime_input.a830_rfc3 && frane_a830_rfc4_enabled(device);

         if (runtime_input.a830_bw2) {""",
     "fallback to RFC3 when disabled")

edit(auto,
     "   std::atomic<uint32_t> frane_a830_v2_tail_word { 0 };",
     """   std::atomic<uint32_t> frane_a830_v2_tail_word { 0 };
   /* Submit thread derives volatility from completed timestamp results.
    * Recording threads see only a relaxed atomic 32-bit snapshot.
    */
   std::atomic<uint32_t> frane_a830_rfc4_vol_word { 0 };""",
     "per-RP compact timestamp volatility memory")

edit(auto,
     """            if (gmem_runtime_input->a830_rfc3) {
               const auto guard = frane_a830_rfc3_select(""",
     """            if (gmem_runtime_input->a830_rfc3 &&
                gmem_runtime_input->a830_rfc4) {
               const auto learned = frane_a830_rfc4_select(
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
               if (learned.owns) {
                  *measure = learned.measure;
                  if (rfc2_reason)
                     *rfc2_reason = learned.audit
                        ? FRANE_A830_RFC2_REGIME_AUDIT
                        : FRANE_A830_RFC2_REGIME_LEARNED;
                  return learned.sysmem ? render_mode::SYSMEM
                                        : render_mode::GMEM;
               }
            } else if (gmem_runtime_input->a830_rfc3) {
               const auto guard = frane_a830_rfc3_select(""",
     "adaptive choice before SMART and original RFC3 A/B fallback")

edit(auto,
     """         if (entry.sysmem) {
            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(rp_duration);""",
     """         if (entry.frane_smart_sample &&
             frane_a830_rfc4_enabled(at.device)) {
            /* Use pre-update EMA to detect real scene changes, not the
             * just-updated EMA which would dilute the surprise.
             */
            const uint32_t previous_count = entry.sysmem
               ? sysmem_rp_average.count : gmem_rp_average.count;
            const uint64_t previous_average = entry.sysmem
               ? sysmem_rp_average.get() : gmem_rp_average.get();
            const uint32_t previous_vol = frane_a830_rfc4_vol_word.load(
               std::memory_order_relaxed);
            frane_a830_rfc4_vol_word.store(
               frane_a830_rfc4_update_volatility(
                  previous_vol, entry.sysmem, previous_average, rp_duration,
                  previous_count),
               std::memory_order_relaxed);
         }
         if (entry.sysmem) {
            sysmem_rp_average.add(rp_duration);
         } else {
            gmem_rp_average.add(rp_duration);""",
     "learn per-mode surprise from measured GPU timestamps")

rfc2=V/"frane_a830_rfc2.h"
edit(rfc2,
     "   FRANE_A830_RFC2_REGIME_AUDIT = 8,",
     "   FRANE_A830_RFC2_REGIME_AUDIT = 8,\n   FRANE_A830_RFC2_REGIME_LEARNED = 9,",
     "add RFC4 choice source")
edit(rfc2,
     """   case FRANE_A830_RFC2_REGIME_AUDIT: return "REGIME_AUDIT";""",
     """   case FRANE_A830_RFC2_REGIME_AUDIT: return "REGIME_AUDIT";
   case FRANE_A830_RFC2_REGIME_LEARNED: return "REGIME_LEARNED";""",
     "name learned decisions in trace")
edit(rfc2,
     "#include <cstdlib>",
     "#include <cstdlib>\n#include <ctime>",
     "session-id timestamp support")
edit(rfc2,
     """   if (r.is_timing) {
      if (((r.occurrence - 1u) & 7u) != 0)
         return;
   } else if (((r.occurrence - 1u) & 63u) != 0 &&
              !(r.measure && ((r.occurrence - 1u) & 15u) == 0u)) {
      return;
   }""",
     """   if (r.is_timing) {
      /* RFC3 sampled only occurrence=1 (mod 8), missing the
       * measured guard cadence at 0 (mod 8/16/32). Use measured-event
       * sequence independent of occurrence phase.
       */
      static std::atomic<uint32_t> measured_events{0};
      if ((measured_events.fetch_add(1, std::memory_order_relaxed) & 3u) != 0)
         return;
   } else if (((r.occurrence - 1u) & 63u) != 0 &&
              !(r.measure && (r.occurrence & 7u) == 0u)) {
      return;
   }""",
     "remove logger phase aliasing with measurement cadence")
edit(rfc2,
     """   struct stat info{};
   if (fstat(fileno(f), &info) == 0 && info.st_size == 0)
      std::fputs(
         "version,event,rp_hash,occurrence,context_sig,source,mode,measure,"
         "gpu_ticks,sys_ema_ticks,gmem_ema_ticks,sys_samples,gmem_samples,"
         "pass_pixels,tile_pixels,drawcalls,sys_cpp,gmem_cpp,"
         "bw2_score,history_score,history_pairs\\n", f);
   std::fprintf(f, "2,%s,%016llx,%u,%016llx,%s,%s,%u,"
                   "%llu,%llu,%llu,%u,%u,%llu,%llu,%u,%u,%u,%d,%d,%u\\n",
      r.is_timing ? "TIMING" : "DECISION",
      (unsigned long long)r.hash, r.occurrence,""",
     """   /* A process-local tag stops offline joining of decisions from
    * separate appended launches that reset each RP occurrence counter.
    */
   static const uint64_t session_id = []() {
      struct timespec ts{};
      clock_gettime(CLOCK_MONOTONIC, &ts);
      return (uint64_t(uint32_t(getpid())) << 32) ^
             (uint64_t(ts.tv_sec) * UINT64_C(1000000007)) ^
             uint64_t(ts.tv_nsec);
   }();
   struct stat info{};
   if (fstat(fileno(f), &info) == 0 && info.st_size == 0)
      std::fputs(
         "version,session_id,event,rp_hash,occurrence,context_sig,source,mode,measure,"
         "gpu_ticks,sys_ema_ticks,gmem_ema_ticks,sys_samples,gmem_samples,"
         "pass_pixels,tile_pixels,drawcalls,sys_cpp,gmem_cpp,"
         "bw2_score,history_score,history_pairs\\n", f);
   std::fprintf(f, "4,%016llx,%s,%016llx,%u,%016llx,%s,%s,%u,"
                   "%llu,%llu,%llu,%u,%u,%llu,%llu,%u,%u,%u,%d,%d,%u\\n",
      (unsigned long long)session_id,
      r.is_timing ? "TIMING" : "DECISION",
      (unsigned long long)r.hash, r.occurrence,""",
     "new CSV schema with per-process session and GPU tick correctness")

edit(V/"tu_device.cc",
     "Turnip-Drnas A830 S2-RFC3 Measured Guard / Mesa ",
     "Turnip-Drnas A830 S2-RFC4 Adaptive Learning / Mesa ",
     "display RFC4 identity")

after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in ROOT.rglob("*") if p.is_file()}
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={"vulkan/frane_a830_rfc4.h","vulkan/frane_a830_rfc2.h",
          "vulkan/frane_mesa_26318_a810_smart_gmem.h",
          "vulkan/tu_autotune.cc","vulkan/tu_device.cc"}
if changed!=expected:
    raise SystemExit(f"RFC4 changed out of scope: {sorted(changed^expected)}")
print("RFC4 PASS source scope + bidirectional learning + session-indexed tracing",flush=True)
