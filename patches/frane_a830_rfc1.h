/* SPDX-License-Identifier: MIT
 * RFC1 - A830 Render Feature Cache & opt-in CSV trace.
 * Exact RP history is not replaced. A compact feature signature is diagnostic
 * only; never used for GPU safety or cross-pass sharing.
 */
#ifndef FRANE_A830_RFC1_H
#define FRANE_A830_RFC1_H
#include "frane_mesa_26318_a810_smart_gmem.h"
#include <atomic>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <mutex>
#include <sys/stat.h>
#include <unistd.h>

/* Run only when explicitly enabled; no disk activity in the default path. */
static inline const char *
frane_a830_rfc1_trace_path(void)
{
   static const char *path = std::getenv("TU_FRANE_A830_TRACE_PATH");
   return path && path[0] == '/' && path[1] ? path : nullptr;
}

static inline uint64_t
frane_a830_rfc1_fingerprint(const frane_26318_smart_gmem_input &in)
{
   /* Quantized, semantic render features: this is intentionally NOT an RP
    * identity key. Use exact Mesa rp_key when retrieving measured history.
    * FNV-1a for compact, reproducible grouping in offline CSV analysis.
    */
   uint64_t h = UINT64_C(14695981039346656037);
   const auto add = [&h](uint64_t x) {
      h ^= x;
      h *= UINT64_C(1099511628211);
   };
   const uint64_t tiles = in.selected_tile_pixels ?
      (in.layout.pass_pixels / in.selected_tile_pixels +
       (in.layout.pass_pixels % in.selected_tile_pixels != 0)) : 0;
   add(in.layout.pass_pixels / 16384u);
   add(in.selected_tile_pixels / 4096u);
   add(tiles > 64 ? 65 : tiles);
   add(tiles ? (in.layout.drawcalls / tiles > 32 ?
                33 : in.layout.drawcalls / tiles) : 0);
   add(in.sysmem_bandwidth_per_pixel ?
       ((uint64_t(in.gmem_bandwidth_per_pixel) * 16u /
         in.sysmem_bandwidth_per_pixel) > 63 ? 63 :
        uint64_t(in.gmem_bandwidth_per_pixel) * 16u /
        in.sysmem_bandwidth_per_pixel) : 0);
   add(in.peak_live_cpp);
   add(in.peak_live_planes);
   add(in.layout.usable_gmem / (256u * 1024u));
   return h;
}

static inline void
frane_a830_rfc1_trace(uint64_t rp_hash, uint32_t occurrence,
                       const frane_26318_smart_gmem_input &in,
                       bool sysmem, bool measured)
{
   const char *path = frane_a830_rfc1_trace_path();
   if (!path || !in.layout.pass_pixels ||
       ((occurrence - 1u) & 63u) != 0u)
      return;

   /* Cap output to keep experimental runs bounded. No allocations, file
    * handles or locks while logging is disabled. Max 2048 samples per process.
    */
   static std::atomic<uint32_t> samples{0};
   if (samples.fetch_add(1, std::memory_order_relaxed) >= 2048)
      return;

   static std::mutex io_mutex;
   std::lock_guard<std::mutex> guard(io_mutex);
   FILE *f = std::fopen(path, "a");
   if (!f) {
      static bool warned = false; // guarded by io_mutex
      if (!warned) {
         std::fprintf(stderr, "A830 RFC1 trace: cannot open %s (errno=%d). "
                      "Use an absolute writable Android/Linux path.\n", path, errno);
         warned = true;
      }
      return;
   }
   struct stat st{};
   if (fstat(fileno(f), &st) == 0 && st.st_size == 0)
      std::fputs("version,rp_hash,context_sig,occurrence,pass_pixels,tile_pixels,"
                 "capacity_pixels,drawcalls,sys_cpp,gmem_cpp,peak_live_cpp,"
                 "peak_planes,history_score,history_pairs,measured_score,"
                 "bw2_delta,mode,measure\n", f);

   const uint64_t sig = frane_a830_rfc1_fingerprint(in);
   const auto &bw2 = in.a830_rfc_cached_bw2;
   std::fprintf(f, "1,%016llx,%016llx,%u,%llu,%llu,%llu,%u,%u,%u,%u,%u,%d,%u,%u,%d,%s,%u\n",
      (unsigned long long)rp_hash,
      (unsigned long long)sig,
      occurrence,
      (unsigned long long)in.layout.pass_pixels,
      (unsigned long long)in.selected_tile_pixels,
      (unsigned long long)in.allocator_capacity_pixels,
      in.layout.drawcalls,
      in.sysmem_bandwidth_per_pixel,
      in.gmem_bandwidth_per_pixel,
      in.peak_live_cpp,
      in.peak_live_planes,
      int(in.a830_history_score),
      unsigned(in.a830_history_pairs),
      unsigned(in.a830_measured_score),
      in.a830_rfc_has_cache ? int(bw2.score_delta) : 999,
      sysmem ? "SYSMEM" : "GMEM",
      measured ? 1u : 0u);
   std::fclose(f);
}
#endif
