/* SPDX-License-Identifier: MIT
 * A810 S Ultimate v1.2 S1 bandwidth probe.
 * Buffered, sampled diagnostics; no GPU query or render-policy changes.
 */
#ifndef FRANE_A810_S1_BANDWIDTH_PROBE_H
#define FRANE_A810_S1_BANDWIDTH_PROBE_H
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <sys/stat.h>
#include <time.h>

static inline const char *frane_s1bp_path()
{
   static const char *const p = std::getenv("TU_FRANE_S1BP_TRACE_PATH");
   return p && p[0] == '/' && p[1] ? p : nullptr;
}

struct frane_s1bp_row {
   uint64_t rp_hash = 0, pixels = 0, tiles = 0;
   uint32_t drawcalls = 0, sys_cpp = 0, gmem_cpp = 0;
   uint32_t profiled_sys_pct = 0, at3_pairs = 0, at3_noise_q8 = 0;
   int at3_score = 0;
   uint8_t structure_score = 0, runtime_score = 0;
   bool zs = false, eligible = false, runtime_armed = false;
   bool s1_override = false, s1_sysmem = false;
   bool final_sysmem = false, measure = false, at4_probe = false, v3_used = false;
   const char *final_source = "UNKNOWN";
};

static inline uint64_t frane_s1bp_estimate(uint64_t pixels, uint32_t cpp)
{
   return cpp && pixels > UINT64_MAX / cpp ? UINT64_MAX : pixels * cpp;
}

static inline uint64_t frane_s1bp_millis()
{
   struct timespec t {};
   if (clock_gettime(CLOCK_MONOTONIC, &t) != 0)
      return 0;
   return uint64_t(t.tv_sec) * 1000u + uint64_t(t.tv_nsec) / 1000000u;
}

struct frane_s1bp_buffer {
   static constexpr uint32_t N = 16;
   std::mutex mutex;
   FILE *file = nullptr;
   bool failed = false;
   uint32_t used = 0;
   uint64_t last_flush_ms = 0;
   char entries[N][640] {};

   void flush_locked(const char *path)
   {
      if (!used || failed) return;
      if (!file) {
         file = std::fopen(path, "a");
         if (!file) { failed = true; used = 0; return; }
         struct stat st {};
         if (fstat(fileno(file), &st) == 0 && st.st_size == 0)
            std::fputs("v,seq,rp_hash,pass_pixels,tiles,drawcalls,sys_cpp,gmem_cpp,sys_est_bytes,gmem_est_bytes,sys_est_known,gmem_est_known,zs,layout_eligible,structure_score,s1_armed,s1_score,profiled_sys_pct,s1_override,s1_select_sysmem,final_mode,final_source,measure,at4_probe,v3_used,at3_score,at3_pairs,at3_noise_q8\n",file);
      }
      for (uint32_t i=0; i<used; ++i)
         std::fputs(entries[i],file);
      std::fflush(file);
      used = 0;
      last_flush_ms = frane_s1bp_millis();
   }

   void append(const char *path, uint64_t seq, const frane_s1bp_row &r)
   {
      std::lock_guard<std::mutex> guard(mutex);
      if (failed) return;
      std::snprintf(entries[used],sizeof(entries[used]),
         "2,%llu,%016llx,%llu,%llu,%u,%u,%u,%llu,%llu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%s,%s,%u,%u,%u,%d,%u,%u\n",
         static_cast<unsigned long long>(seq),
         static_cast<unsigned long long>(r.rp_hash),
         static_cast<unsigned long long>(r.pixels),
         static_cast<unsigned long long>(r.tiles),
         r.drawcalls,r.sys_cpp,r.gmem_cpp,
         static_cast<unsigned long long>(frane_s1bp_estimate(r.pixels,r.sys_cpp)),
         static_cast<unsigned long long>(frane_s1bp_estimate(r.pixels,r.gmem_cpp)),
         unsigned(r.sys_cpp!=0),unsigned(r.gmem_cpp!=0),
         unsigned(r.zs),unsigned(r.eligible),unsigned(r.structure_score),
         unsigned(r.runtime_armed),unsigned(r.runtime_score),r.profiled_sys_pct,
         unsigned(r.s1_override),unsigned(r.s1_sysmem),
         r.final_sysmem ? "SYSMEM" : "GMEM", r.final_source,
         unsigned(r.measure),unsigned(r.at4_probe),unsigned(r.v3_used),
         r.at3_score,r.at3_pairs,r.at3_noise_q8);
      ++used;
      const uint64_t now=frane_s1bp_millis();
      if (!last_flush_ms) last_flush_ms=now;
      if (used==N || (now>=last_flush_ms && now-last_flush_ms>=2500u))
         flush_locked(path);
   }

   ~frane_s1bp_buffer()
   {
      const char *path=frane_s1bp_path();
      if (path && !failed) flush_locked(path);
      if (file) std::fclose(file);
   }
};

static inline uint64_t frane_s1bp_take_sample()
{
   if (!frane_s1bp_path()) return 0;
   static std::atomic<uint64_t> count{0};
   const uint64_t seq=count.fetch_add(1,std::memory_order_relaxed)+1;
   if (seq>4000000ull) return 0;
   return seq<=8u || (seq & 63u)==0u ? seq : 0;
}

static inline void frane_s1bp_trace(uint64_t seq,const frane_s1bp_row &r)
{
   const char *path=frane_s1bp_path();
   if (!path || !seq) return;
   static frane_s1bp_buffer writer;
   writer.append(path,seq,r);
}
#endif
