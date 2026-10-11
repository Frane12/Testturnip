/* SPDX-License-Identifier: MIT
 * A810 CP1: passive, opt-in CPU queue submission breakdown.
 * No GPU counter queries, no forced waits, and no timing calls unless
 * an explicit, absolute TU_FRANE_A810_CP1_TRACE_PATH is configured.
 */
#ifndef FRANE_A810_CP1_H
#define FRANE_A810_CP1_H

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <mutex>
#include <time.h>
#include <sys/stat.h>
#include <unistd.h>

static inline bool
frane_cp1_a810(const struct tu_device *device)
{
   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static inline bool
frane_cp1_zero_entries_enabled()
{
   static const bool enabled = []() {
      const char *env = std::getenv("TU_FRANE_CP1_ZERO_SKIP");
      return !env || env[0] != '0' || env[1] != '\0';
   }();
   return enabled;
}

static inline const char *
frane_cp1_path()
{
   static const char *const path =
      std::getenv("TU_FRANE_A810_CP1_TRACE_PATH");
   return path && path[0] == '/' && path[1] ? path : nullptr;
}

static inline uint64_t
frane_cp1_now_ns()
{
   struct timespec ts {};
   clock_gettime(CLOCK_MONOTONIC, &ts);
   return uint64_t(ts.tv_sec) * UINT64_C(1000000000) +
          uint64_t(ts.tv_nsec);
}

struct frane_cp1_trace {
   bool enabled = false;
   uint32_t sample = 0;
   uint32_t cmdbufs = 0;
   uint32_t cmd_entries = 0;
   uint64_t begin = 0;
   uint64_t locked = 0;
   uint64_t patched = 0;
   uint64_t gathered = 0;
   uint64_t autotuned = 0;
   uint64_t before_kernel = 0;
   uint64_t after_kernel = 0;
   uint64_t end = 0;
};

static inline frane_cp1_trace
frane_cp1_begin(const struct tu_device *device, uint32_t cmdbufs)
{
   frane_cp1_trace t {};
   if (!frane_cp1_a810(device) || !frane_cp1_path())
      return t;
   static std::atomic<uint32_t> seq { 0 };
   const uint32_t n = seq.fetch_add(1, std::memory_order_relaxed) + 1;
   if (n > 16 && (n & 15u) != 0)
      return t;
   t.enabled = true;
   t.sample = n;
   t.cmdbufs = cmdbufs;
   t.begin = frane_cp1_now_ns();
   return t;
}

static inline void
frane_cp1_emit(const frane_cp1_trace &t)
{
   if (!t.enabled || !t.begin || !t.end)
      return;
   static std::mutex io_mutex;
   std::lock_guard<std::mutex> lock(io_mutex);
   const char *path = frane_cp1_path();
   FILE *f = std::fopen(path, "a");
   if (!f)
      return;
   struct stat st {};
   if (fstat(fileno(f), &st) == 0 && st.st_size == 0)
      std::fputs("schema,sample,cmdbufs,cmd_entries,lock_wait_ns,"
                 "patch_ns,entries_ns,autotune_ns,pre_kernel_ns,"
                 "kernel_ns,post_kernel_ns,total_ns\n", f);
   const auto d = [](uint64_t e, uint64_t b) {
      return e >= b ? e - b : 0;
   };
   std::fprintf(f, "1,%u,%u,%u,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu\n",
      t.sample, t.cmdbufs, t.cmd_entries,
      (unsigned long long)d(t.locked, t.begin),
      (unsigned long long)d(t.patched, t.locked),
      (unsigned long long)d(t.gathered, t.patched),
      (unsigned long long)d(t.autotuned, t.gathered),
      (unsigned long long)d(t.before_kernel, t.autotuned),
      (unsigned long long)d(t.after_kernel, t.before_kernel),
      (unsigned long long)d(t.end, t.after_kernel),
      (unsigned long long)d(t.end, t.begin));
   std::fclose(f);
}
#endif
