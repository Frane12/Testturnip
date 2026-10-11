/* SPDX-License-Identifier: MIT
 * ATUltimate A810: opt-in, bounded, sampled rendering context table CSV.
 * Only loads EXISTING atomic AT3 snapshots. No GPU query or policy changes.
 * Heavy I/O exists ONLY when TU_FRANE_ATU_CONTEXT_TRACE_PATH is set.
 */
#ifndef FRANE_A810_ATULTIMATE_TRACE_H
#define FRANE_A810_ATULTIMATE_TRACE_H
#include "frane_a810_atultimate.h"
#include <atomic>
#include <cerrno>
#include <cinttypes>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <sys/stat.h>
#include <unistd.h>

static inline const char *
frane_atu_trace_path()
{
   static const char *const path = std::getenv("TU_FRANE_ATU_CONTEXT_TRACE_PATH");
   return path && path[0] == '/' && path[1] ? path : nullptr;
}

struct frane_atu_trace_row {
   uint64_t hash = 0;
   uint32_t occurrence = 0;
   uint32_t probability = 0;
   uint16_t signature = 0;
   frane_s1at1_context_input in {};
   frane_s1at3_snapshot s {};
   bool mode_sysmem = false;
   bool measure = false;
   bool eligible = false;
   bool safety_forced = false;
   bool depth_overrode = false;
   bool at4_controlled = false;
   bool prior_rejected = false;
   const char *source = "PROFILED";
};

/* Caller may copy snapshots with relaxed loads: every 64-bit snapshot is
 * atomic, but a whole 16-slot TABLE dump is not one simultaneous GPU frame.
 * The signature remains valid even for decisions without a timestamp.
 */
static inline void
frane_atu_trace(const frane_atu_trace_row &r,
                const std::atomic<uint64_t> *slots = nullptr)
{
   const char *path = frane_atu_trace_path();
   if (!path || !r.occurrence)
      return;
   const bool record = r.occurrence <= 4u ||
      (r.occurrence & 31u) == 0u ||
      (r.prior_rejected && (r.occurrence & 7u) == 0u);
   const bool dump = slots &&
      (r.occurrence == 1u || (r.occurrence & 255u) == 0u);
   if (!record && !dump)
      return;
   static std::atomic<uint32_t> budget{0};
   const uint32_t units = (record ? 1u : 0u) +
      (dump ? FRANE_AT3_ENTRIES : 0u);
   if (budget.fetch_add(units, std::memory_order_relaxed) >= 75000u)
      return;
   static std::mutex io_mutex;
   std::lock_guard<std::mutex> lock(io_mutex);
   FILE *f = std::fopen(path, "a");
   if (!f) {
      static bool warned = false;
      if (!warned) {
         std::fprintf(stderr, "A810 ATUltimate context CSV: cannot open %s errno=%d\n",path,errno);
         warned = true;
      }
      return;
   }
   struct stat st{};
   if (fstat(fileno(f), &st) == 0 && st.st_size == 0)
      std::fputs(
         "v,event,rp_hash,occurrence,signature,slot,catalog,pass_pixels,tiles,"
         "drawcalls,sys_cpp,gmem_cpp,zs,profiled_sys_percent,final_mode,"
         "measure,eligible,source,score,volatility,sys_samples,gmem_samples,"
         "sys_stale,gmem_stale,lower_saving_us,noise_q8,history_hit,"
         "diagnosis,prior_rejected\n",f);
   if (record) {
      const bool hit = r.signature && r.signature == r.s.signature;
      const unsigned paired = std::min(r.s.samples[0], r.s.samples[1]);
      const bool conflicting = hit && paired >= 2 &&
         std::abs(int(r.s.score)) >= 8 &&
         r.s.at7_saving_4us >= 40 && r.s.at7_noise_q8 <= 80 &&
         r.s.volatility <= 3 && !r.s.stale[0] && !r.s.stale[1] &&
         r.mode_sysmem != (r.s.score < 0);
      const char *diagnosis = r.safety_forced ? "SAFETY_OVERRIDE" :
         r.depth_overrode ? "DEPTH_OVERRIDE" :
         r.prior_rejected ? "PRIOR_CONFLICT_BLOCKED" :
         r.at4_controlled && r.measure ? "AT4_PROBE" :
         !hit ? "CONTEXT_MISS" : conflicting ? "MEASURED_DISAGREEMENT" :
         paired < 2 ? "LEARNING" :
         r.s.stale[0] || r.s.stale[1] ? "STALE_HISTORY" :
         r.s.volatility > 3 ? "VOLATILE_HISTORY" : "OK";
      const auto c = frane_s1at1_catalog_for(r.in);
      std::fprintf(f,
         "2,DECISION,%016llx,%u,%u,-1,%u,%llu,%llu,%u,%u,%u,%u,%u,%s,%u,%u,%s,%d,%u,%u,%u,%u,%u,%u,%u,%u,%s,%u\n",
         static_cast<unsigned long long>(r.hash),r.occurrence,
         unsigned(r.signature),unsigned(c.id),
         static_cast<unsigned long long>(r.in.pass_pixels),
         static_cast<unsigned long long>(r.in.estimated_tiles),
         r.in.drawcalls,r.in.sysmem_bandwidth_per_pixel,
         r.in.gmem_bandwidth_per_pixel,unsigned(r.in.zs_load_store),
         r.probability,r.mode_sysmem ? "SYSMEM":"GMEM",
         unsigned(r.measure),unsigned(r.eligible),r.source,
         int(r.s.score),unsigned(r.s.volatility),
         unsigned(r.s.samples[0]),unsigned(r.s.samples[1]),
         unsigned(r.s.stale[0]),unsigned(r.s.stale[1]),
         unsigned(r.s.at7_saving_4us)*4u,unsigned(r.s.at7_noise_q8),
         unsigned(hit),diagnosis,unsigned(r.prior_rejected));
   }
   if (dump) {
      for (unsigned i=0; i<FRANE_AT3_ENTRIES; i++) {
         const auto s=frane_s1at3_unpack(
            slots[i].load(std::memory_order_relaxed));
         if (!s.signature)
            continue;
         std::fprintf(f,
            "2,TABLE,%016llx,%u,%u,%u,0,0,0,0,0,0,0,0,NA,0,0,TABLE_SNAPSHOT,%d,%u,%u,%u,%u,%u,%u,%u,1,SLOT_SNAPSHOT,0\n",
            static_cast<unsigned long long>(r.hash),
            r.occurrence,unsigned(s.signature),i,int(s.score),
            unsigned(s.volatility),unsigned(s.samples[0]),
            unsigned(s.samples[1]),unsigned(s.stale[0]),
            unsigned(s.stale[1]),unsigned(s.at7_saving_4us)*4u,
            unsigned(s.at7_noise_q8));
      }
   }
   std::fclose(f);
}
#endif
