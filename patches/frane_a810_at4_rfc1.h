/* SPDX-License-Identifier: MIT
 * A810 AT4 RFC1: opt-in, read-only, bounded render-mode/real-GPU-time CSV.
 * No logging unless TU_FRANE_A810_RFC1_TRACE_PATH is an absolute path.
 * Native file access requires write permission inside the emulator app.
 */
#ifndef FRANE_A810_AT4_RFC1_H
#define FRANE_A810_AT4_RFC1_H

#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <sys/stat.h>
#include <unistd.h>

static inline const char *
frane_a810_rfc1_path()
{
   static const char *const path = std::getenv("TU_FRANE_A810_RFC1_TRACE_PATH");
   return path && path[0] == '/' && path[1] ? path : nullptr;
}

struct frane_a810_rfc1_row {
   uint64_t rp_hash = 0;
   uint64_t gpu_ns = 0;
   uint64_t sys_avg_ns = 0;
   uint64_t gmem_avg_ns = 0;
   uint64_t pass_pixels = 0;
   uint64_t selected_tiles = 0;
   uint64_t usable_gmem_bytes = 0;
   uint32_t occurrence = 0;
   uint32_t drawcalls = 0;
   uint32_t sys_cpp = 0;
   uint32_t gmem_cpp = 0;
   uint32_t sys_samples = 0;
   uint32_t gmem_samples = 0;
   uint32_t probability = 0;
   uint16_t signature = 0;
   const char *selector = "PROFILED_OR_S1";
   bool sysmem = false;
   bool measure = false;
   bool eligible = false;
   bool at4_context = false;
   bool is_timing = false;
};

/* Bounded opt-in events. Every TIMING occurrence is also eligible for a
 * DECISION event. An application may reuse the same RP entry across frames:
 * TIMING rows then represent separate measured executions of that entry.
 */
static inline void
frane_a810_rfc1_emit(const frane_a810_rfc1_row &r)
{
   const char *path = frane_a810_rfc1_path();
   if (!path || !r.occurrence)
      return;
   const bool sampled = r.occurrence <= 4u ||
      ((r.occurrence & 63u) == 0u) ||
      (r.measure && ((r.occurrence & 15u) == 0u));
   if (!sampled)
      return;
   static std::atomic<uint32_t> emitted{0};
   if (emitted.fetch_add(1, std::memory_order_relaxed) >= 8192u)
      return;
   static std::mutex io_mutex;
   std::lock_guard<std::mutex> lock(io_mutex);
   FILE *f = std::fopen(path, "a");
   if (!f) {
      static bool warned = false;
      if (!warned) {
         std::fprintf(stderr, "A810 RFC1: cannot open %s errno=%d\n", path, errno);
         warned = true;
      }
      return;
   }
   struct stat st{};
   if (fstat(fileno(f), &st) == 0 && st.st_size == 0)
      std::fputs(
         "v,event,rp_hash,occurrence,signature,source,mode,measure,"
         "eligible,at4_context,probability,pass_pixels,selected_tiles,"
         "drawcalls,sys_cpp,gmem_cpp,usable_gmem_bytes,gpu_ns,"
         "sys_avg_ns,gmem_avg_ns,sys_samples,gmem_samples\n", f);
   std::fprintf(f,
      "1,%s,%016llx,%u,%u,%s,%s,%u,%u,%u,%u,%llu,%llu,%u,%u,%u,%llu,"
      "%llu,%llu,%llu,%u,%u\n",
      r.is_timing ? "TIMING" : "DECISION",
      static_cast<unsigned long long>(r.rp_hash), r.occurrence,
      unsigned(r.signature), r.is_timing ? "GPU_TIMESTAMP" : r.selector,
      r.sysmem ? "SYSMEM" : "GMEM", unsigned(r.measure),
      unsigned(r.eligible), unsigned(r.at4_context), r.probability,
      static_cast<unsigned long long>(r.pass_pixels),
      static_cast<unsigned long long>(r.selected_tiles),
      r.drawcalls, r.sys_cpp, r.gmem_cpp,
      static_cast<unsigned long long>(r.usable_gmem_bytes),
      static_cast<unsigned long long>(r.gpu_ns),
      static_cast<unsigned long long>(r.sys_avg_ns),
      static_cast<unsigned long long>(r.gmem_avg_ns),
      r.sys_samples, r.gmem_samples);
   std::fclose(f);
}

static inline void
frane_a810_rfc1_decision(uint64_t hash, uint32_t occurrence,
                         uint16_t signature, const char *source, bool sysmem,
                         bool measure, bool eligible, bool at4_context,
                         uint32_t probability, uint64_t pass_pixels,
                         uint64_t selected_tiles, uint32_t drawcalls,
                         uint32_t sys_cpp, uint32_t gmem_cpp,
                         uint64_t usable_gmem_bytes)
{
   if (!frane_a810_rfc1_path())
      return;
   frane_a810_rfc1_row row{};
   row.rp_hash = hash;
   row.occurrence = occurrence;
   row.signature = signature;
   row.selector = source;
   row.sysmem = sysmem;
   row.measure = measure;
   row.eligible = eligible;
   row.at4_context = at4_context;
   row.probability = probability;
   row.pass_pixels = pass_pixels;
   row.selected_tiles = selected_tiles;
   row.drawcalls = drawcalls;
   row.sys_cpp = sys_cpp;
   row.gmem_cpp = gmem_cpp;
   row.usable_gmem_bytes = usable_gmem_bytes;
   frane_a810_rfc1_emit(row);
}

static inline void
frane_a810_rfc1_timing(uint64_t hash, uint32_t occurrence,
                       uint16_t signature, bool sysmem, uint64_t duration_ns,
                       uint64_t sys_avg_ns, uint64_t gmem_avg_ns,
                       uint32_t sys_count, uint32_t gmem_count)
{
   if (!frane_a810_rfc1_path() || !duration_ns || !occurrence)
      return;
   frane_a810_rfc1_row row{};
   row.rp_hash = hash;
   row.occurrence = occurrence;
   row.signature = signature;
   row.sysmem = sysmem;
   row.measure = true;
   row.is_timing = true;
   row.gpu_ns = duration_ns;
   row.sys_avg_ns = sys_avg_ns;
   row.gmem_avg_ns = gmem_avg_ns;
   row.sys_samples = sys_count;
   row.gmem_samples = gmem_count;
   frane_a810_rfc1_emit(row);
}
#endif
