/* SPDX-License-Identifier: MIT
 * Optional sampled CPU timing of Vulkan pipeline creations.
 * CPU wall and CPU thread times, not GPU execution or shader-cache misses.
 */
#ifndef FRANE_A810_PIPELINE_PROBE_H
#define FRANE_A810_PIPELINE_PROBE_H
#include "frane_a810_cpu_pipeline_probe.h"
#include <atomic>
#include <cstdint>

static inline const char *frane_pipeline_trace_path()
{
   static const char *const p=std::getenv("TU_FRANE_PIPELINE_TRACE_PATH");
   return p && p[0]=='/' && p[1] ? p : nullptr;
}
static inline uint64_t frane_pipeline_sample()
{
   if (!frane_pipeline_trace_path()) return 0;
   static std::atomic<uint64_t> counter{0};
   uint64_t n=counter.fetch_add(1,std::memory_order_relaxed)+1;
   return n<=128 || (n<=65536 && (n&7u)==0) ? n : 0;
}
struct frane_pipeline_stamp {
   uint64_t seq=0;
   uint64_t wall_ns=0;
   uint64_t cpu_ns=0;
};
static inline frane_pipeline_stamp frane_pipeline_begin()
{
   frane_pipeline_stamp t {};
   t.seq=frane_pipeline_sample();
   if (t.seq) {
      t.wall_ns=frane_cpu_clock_ns(CLOCK_MONOTONIC);
      t.cpu_ns=frane_cpu_clock_ns(CLOCK_THREAD_CPUTIME_ID);
   }
   return t;
}
static inline void frane_pipeline_end(frane_pipeline_stamp t,
                                      const char *type,
                                      unsigned count, int result)
{
   const char *path=frane_pipeline_trace_path();
   if (!t.seq || !path) return;
   const uint64_t end=frane_cpu_clock_ns(CLOCK_MONOTONIC);
   const uint64_t cpu_end=frane_cpu_clock_ns(CLOCK_THREAD_CPUTIME_ID);
   char line[384];
   std::snprintf(line,sizeof(line),
      "1,%llu,%llu,%s,%u,%llu,%llu,%d,%llu\n",
      (unsigned long long)t.seq,(unsigned long long)end,type,
      count,(unsigned long long)frane_cpu_elapsed_us(t.wall_ns,end),
      (unsigned long long)frane_cpu_elapsed_us(t.cpu_ns,cpu_end),
      result,(unsigned long long)frane_cpu_rss_kib());
   static frane_cpu_csv_writer writer(path,
     "v,seq,mono_end_ns,type,requested_count,wall_us,"
     "thread_cpu_us,vk_result,process_rss_kib\n");
   writer.append(line);
}
#endif
