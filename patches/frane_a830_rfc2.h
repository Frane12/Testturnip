/* SPDX-License-Identifier: MIT
 * A830 RFC2: read-only GPU timestamp and render-mode-source diagnostics.
 * Mesa RP history/timestamp accounting remains authoritative.
 *
 * The native Android/Linux CSV path is opt-in, independent of RFC1.
 * No logging, locking or allocations when the path is not configured.
 */
#ifndef FRANE_A830_RFC2_H
#define FRANE_A830_RFC2_H
#include "frane_a830_rfc1.h"
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <sys/stat.h>
#include <unistd.h>

enum frane_a830_rfc2_reason : uint8_t {
   FRANE_A830_RFC2_PROFILED = 0,
   FRANE_A830_RFC2_LOCKED = 1,
   FRANE_A830_RFC2_SMART_V2 = 2,
   FRANE_A830_RFC2_SMART_GMEM = 3,
   FRANE_A830_RFC2_ADAPTIVE = 4,
   FRANE_A830_RFC2_BW2_ROLLBACK = 5,
   FRANE_A830_RFC2_RUNTIME = 6,
};

static inline const char *
frane_a830_rfc2_reason_str(unsigned reason)
{
   switch (reason) {
   case FRANE_A830_RFC2_LOCKED: return "PROFILED_LOCKED";
   case FRANE_A830_RFC2_SMART_V2: return "SMART_V2";
   case FRANE_A830_RFC2_SMART_GMEM: return "SMART_GMEM";
   case FRANE_A830_RFC2_ADAPTIVE: return "ADAPTIVE";
   case FRANE_A830_RFC2_BW2_ROLLBACK: return "BW2_ROLLBACK";
   case FRANE_A830_RFC2_RUNTIME: return "RUNTIME";
   default: return "PROFILED";
   }
}

static inline const char *
frane_a830_rfc2_trace_path()
{
   static const char *path = std::getenv("TU_FRANE_A830_RFC2_TRACE_PATH");
   return path && path[0] == '/' && path[1] ? path : nullptr;
}

struct frane_a830_rfc2_row {
   uint64_t hash = 0;
   uint64_t context_sig = 0;
   uint64_t gpu_ns = 0;
   uint64_t sys_ema_ns = 0;
   uint64_t gmem_ema_ns = 0;
   uint64_t pass_pixels = 0;
   uint64_t tile_pixels = 0;
   uint32_t occurrence = 0;
   uint32_t drawcalls = 0;
   uint32_t sys_cpp = 0;
   uint32_t gmem_cpp = 0;
   uint32_t sys_samples = 0;
   uint32_t gmem_samples = 0;
   int32_t bw2_score = 999;  /* 999 = policy not evaluated */
   int32_t history_score = 0;
   uint32_t history_pairs = 0;
   uint8_t reason = FRANE_A830_RFC2_PROFILED;
   bool sysmem = false;
   bool measure = false;
   bool is_timing = false;
};

static inline void
frane_a830_rfc2_emit(const frane_a830_rfc2_row &r)
{
   const char *path = frane_a830_rfc2_trace_path();
   if (!path || !r.occurrence)
      return;
   /* Keep expensive file I/O rare, and bound disk usage. Timing events
    * are sampled on the GPU-result submit thread (not command recording).
    */
   if (r.is_timing) {
      if (((r.occurrence - 1u) & 7u) != 0)
         return;
   } else if (((r.occurrence - 1u) & 63u) != 0 &&
              !(r.measure && ((r.occurrence - 1u) & 15u) == 0u)) {
      return;
   }
   static std::atomic<uint32_t> budget{0};
   if (budget.fetch_add(1, std::memory_order_relaxed) >= 8192u)
      return;

   static std::mutex write_mutex;
   std::lock_guard<std::mutex> guard(write_mutex);
   FILE *f = std::fopen(path, "a");
   if (!f) {
      static bool warned = false;
      if (!warned) {
         std::fprintf(stderr, "A830 RFC2: cannot open %s errno=%d\n", path, errno);
         warned = true;
      }
      return;
   }
   struct stat info{};
   if (fstat(fileno(f), &info) == 0 && info.st_size == 0)
      std::fputs(
         "version,event,rp_hash,occurrence,context_sig,source,mode,measure,"
         "gpu_ns,sys_ema_ns,gmem_ema_ns,sys_samples,gmem_samples,"
         "pass_pixels,tile_pixels,drawcalls,sys_cpp,gmem_cpp,"
         "bw2_score,history_score,history_pairs\n", f);
   std::fprintf(f, "2,%s,%016llx,%u,%016llx,%s,%s,%u,"
                   "%llu,%llu,%llu,%u,%u,%llu,%llu,%u,%u,%u,%d,%d,%u\n",
      r.is_timing ? "TIMING" : "DECISION",
      (unsigned long long)r.hash, r.occurrence,
      (unsigned long long)r.context_sig,
      r.is_timing ? "GPU_TIMESTAMP" : frane_a830_rfc2_reason_str(r.reason),
      r.sysmem ? "SYSMEM" : "GMEM", r.measure ? 1u : 0u,
      (unsigned long long)r.gpu_ns,
      (unsigned long long)r.sys_ema_ns,
      (unsigned long long)r.gmem_ema_ns,
      r.sys_samples, r.gmem_samples,
      (unsigned long long)r.pass_pixels,
      (unsigned long long)r.tile_pixels,
      r.drawcalls, r.sys_cpp, r.gmem_cpp,
      r.bw2_score, r.history_score, r.history_pairs);
   std::fclose(f);
}

static inline void
frane_a830_rfc2_decision(uint64_t hash, uint32_t occurrence,
                          const frane_26318_smart_gmem_input &in,
                          uint8_t reason, bool sysmem, bool measure)
{
   if (!frane_a830_rfc2_trace_path())
      return;
   frane_a830_rfc2_row row{};
   row.hash = hash;
   row.occurrence = occurrence;
   row.context_sig = frane_a830_rfc1_fingerprint(in);
   row.reason = reason;
   row.sysmem = sysmem;
   row.measure = measure;
   row.pass_pixels = in.layout.pass_pixels;
   row.tile_pixels = in.selected_tile_pixels;
   row.drawcalls = in.layout.drawcalls;
   row.sys_cpp = in.sysmem_bandwidth_per_pixel;
   row.gmem_cpp = in.gmem_bandwidth_per_pixel;
   row.history_score = in.a830_history_score;
   row.history_pairs = in.a830_history_pairs;
   row.bw2_score = in.a830_rfc_has_cache
      ? int(in.a830_rfc_cached_bw2.score_delta) : 999;
   frane_a830_rfc2_emit(row);
}

static inline void
frane_a830_rfc2_timing(uint64_t hash, uint32_t occurrence,
                        bool sysmem, uint64_t gpu_duration_ns,
                        uint64_t sys_average_ns, uint64_t gm_average_ns,
                        uint32_t sys_count, uint32_t gm_count,
                        int32_t history_score, uint32_t history_pairs)
{
   if (!frane_a830_rfc2_trace_path() || !gpu_duration_ns)
      return;
   frane_a830_rfc2_row row{};
   row.hash = hash;
   row.occurrence = occurrence;
   row.is_timing = true;
   row.sysmem = sysmem;
   row.measure = true; /* this was an actual completed GPU timestamp */
   row.gpu_ns = gpu_duration_ns;
   row.sys_ema_ns = sys_average_ns;
   row.gmem_ema_ns = gm_average_ns;
   row.sys_samples = sys_count;
   row.gmem_samples = gm_count;
   row.history_score = history_score;
   row.history_pairs = history_pairs;
   frane_a830_rfc2_emit(row);
}
#endif
