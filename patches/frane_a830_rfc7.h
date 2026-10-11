/* SPDX-License-Identifier: MIT
 * A830 RFC7: opt-in native render-pass bandwidth/phase diagnostics.
 * This is an OBSERVER, not a bandwidth limiter or GMEM/SYSMEM policy.
 * Bytes are geometry/attachment ESTIMATES, not measured DRAM traffic.
 * GPU durations are existing HW timestamp ticks, not nanoseconds.
 */
#ifndef FRANE_A830_RFC7_H
#define FRANE_A830_RFC7_H
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <time.h>
#include <unistd.h>

struct frane_a830_rfc7_row {
   uint64_t rp_hash = 0;
   uint64_t pass_pixels = 0;
   uint64_t tile_pixels = 0;
   uint64_t tiles = 0;
   uint64_t load_cpp = 0;
   uint64_t store_cpp = 0;
   uint64_t clear_cpp = 0;
   uint64_t resolve_cpp = 0;
   uint64_t draw_bw_sample_sum = 0;
   uint64_t gpu_ticks = 0;
   uint64_t render_ticks = 0;
   uint64_t binning_ticks = 0;
   uint64_t max_tile_ticks = 0;
   uint64_t samples_passed = 0;
   uint64_t physical_gmem_bytes = 0;
   uint64_t usable_gmem_bytes = 0;
   uint32_t occurrence = 0;
   uint32_t drawcalls = 0;
   uint32_t attachments = 0;
   uint32_t sys_cpp = 0;
   uint32_t gmem_cpp = 0;
   bool sysmem = false;
   bool measure = false;
   bool timing = false;
   bool has_tile_ticks = false;
   bool has_samples = false;
};

static inline uint64_t
frane_a830_rfc7_sat_mul(uint64_t a, uint64_t b)
{
   return b && a > UINT64_MAX / b ? UINT64_MAX : a * b;
}

static inline const char *
frane_a830_rfc7_path()
{
   static const char *path = std::getenv("TU_FRANE_A830_RFC7_PATH");
   return path && path[0] == '/' && path[1] ? path : nullptr;
}

/* Only the optional diagnostic path instantiates this object. A single
 * buffered FILE avoids fopen/fclose per render-pass sample, and periodic
 * fflush makes the CSV visible while Crysis is still running.
 */
struct frane_a830_rfc7_sink {
   std::mutex mutex;
   FILE *file = nullptr;
   uint32_t rows = 0;
   uint64_t session = 0;
   bool failed = false;

   ~frane_a830_rfc7_sink()
   {
      if (file)
         std::fclose(file);
   }

   void write(const frane_a830_rfc7_row &r, const char *path)
   {
      std::lock_guard<std::mutex> guard(mutex);
      if (rows >= 16384u || failed)
         return;
      if (!file) {
         file = std::fopen(path, "a");
         if (!file) {
            std::fprintf(stderr, "A830 RFC7: cannot write %s errno=%d\n", path, errno);
            failed = true;
            return;
         }
         std::setvbuf(file, nullptr, _IOFBF, 65536);
         struct timespec ts {};
         clock_gettime(CLOCK_MONOTONIC, &ts);
         session = (uint64_t(uint32_t(getpid())) << 32) ^
                   (uint64_t(ts.tv_sec) * UINT64_C(1000000007)) ^
                   uint64_t(ts.tv_nsec);
         if (std::fseek(file, 0, SEEK_END) == 0 && std::ftell(file) == 0)
            std::fputs(
               "version,session,event,rp_hash,occurrence,mode,measure,"
               "pass_pixels,tile_pixels,tiles,drawcalls,attachments,"
               "load_cpp,store_cpp,clear_cpp,resolve_cpp,"
               "est_load_bytes,est_store_bytes,est_clear_bytes,est_resolve_bytes,"
               "draw_bw_per_sample_sum,sys_cpp,gmem_cpp,"
               "physical_gmem_bytes,usable_gmem_bytes,"
               "gpu_ticks,render_ticks,binning_ticks,max_tile_ticks,"
               "has_tile_ticks,samples_passed,has_samples\n", file);
      }
      std::fprintf(file,
          "7,%016llx,%s,%016llx,%u,%s,%u,"
          "%llu,%llu,%llu,%u,%u,"
          "%llu,%llu,%llu,%llu,"
          "%llu,%llu,%llu,%llu,"
          "%llu,%u,%u,"
          "%llu,%llu,"
          "%llu,%llu,%llu,%llu,%u,%llu,%u\n",
          (unsigned long long)session,
          r.timing ? "TIMING" : "DECISION",
          (unsigned long long)r.rp_hash, r.occurrence,
          r.sysmem ? "SYSMEM" : "GMEM", r.measure ? 1u : 0u,
          (unsigned long long)r.pass_pixels,
          (unsigned long long)r.tile_pixels,
          (unsigned long long)r.tiles,
          r.drawcalls, r.attachments,
          (unsigned long long)r.load_cpp,
          (unsigned long long)r.store_cpp,
          (unsigned long long)r.clear_cpp,
          (unsigned long long)r.resolve_cpp,
          (unsigned long long)frane_a830_rfc7_sat_mul(r.pass_pixels, r.load_cpp),
          (unsigned long long)frane_a830_rfc7_sat_mul(r.pass_pixels, r.store_cpp),
          (unsigned long long)frane_a830_rfc7_sat_mul(r.pass_pixels, r.clear_cpp),
          (unsigned long long)frane_a830_rfc7_sat_mul(r.pass_pixels, r.resolve_cpp),
          (unsigned long long)r.draw_bw_sample_sum, r.sys_cpp, r.gmem_cpp,
          (unsigned long long)r.physical_gmem_bytes,
          (unsigned long long)r.usable_gmem_bytes,
          (unsigned long long)r.gpu_ticks,
          (unsigned long long)r.render_ticks,
          (unsigned long long)r.binning_ticks,
          (unsigned long long)r.max_tile_ticks,
          r.has_tile_ticks ? 1u : 0u,
          (unsigned long long)r.samples_passed,
          r.has_samples ? 1u : 0u);
      ++rows;
      if ((rows & 31u) == 0u)
         std::fflush(file);
   }
};

static inline void
frane_a830_rfc7_emit(const frane_a830_rfc7_row &r)
{
   const char *path = frane_a830_rfc7_path();
   if (!path || !r.occurrence)
      return;
   if (r.timing) {
      static std::atomic<uint32_t> timings{0};
      if ((timings.fetch_add(1, std::memory_order_relaxed) & 1u) != 0u)
         return;
   } else if (((r.occurrence - 1u) & 7u) != 0u)
      return;

   static frane_a830_rfc7_sink sink;
   sink.write(r,path);
}
#endif
