/* SPDX-License-Identifier: MIT
 * S Ultimate A810 v1.4: opt-in, bounded CPU command-record/queue probes.
 * No render-mode changes, new GPU queries, or kernel memory counters.
 * CPU times are wall and THREAD_CPUTIME; RSS is process resident memory
 * and MUST NOT be represented as GPU/DRAM bandwidth.
 */
#ifndef FRANE_A810_CPU_PIPELINE_PROBE_H
#define FRANE_A810_CPU_PIPELINE_PROBE_H

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mutex>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <pthread.h>

static inline const char *frane_cpu_trace_path(bool queue)
{
   static const char *const cb = std::getenv("TU_FRANE_CPU_CB_TRACE_PATH");
   static const char *const q = std::getenv("TU_FRANE_CPU_QUEUE_TRACE_PATH");
   const char *p = queue ? q : cb;
   return p && p[0] == '/' && p[1] ? p : nullptr;
}

static inline uint64_t frane_cpu_clock_ns(clockid_t which)
{
   struct timespec ts {};
   if (clock_gettime(which, &ts) != 0) return 0;
   return uint64_t(ts.tv_sec)*1000000000ull + uint64_t(ts.tv_nsec);
}

static inline uint64_t frane_cpu_elapsed_us(uint64_t from, uint64_t to)
{
   return from && to >= from ? (to-from)/1000ull : 0;
}

/* This reads only this process' resident pages. It is NOT DRAM bandwidth,
 * total game memory (other processes!), nor GPU allocation accounting. */
static inline uint64_t frane_cpu_rss_kib()
{
   FILE *f=std::fopen("/proc/self/statm","r");
   if (!f) return 0;
   unsigned long long total=0, resident=0;
   int n=std::fscanf(f,"%llu %llu",&total,&resident);
   std::fclose(f);
   if (n!=2) return 0;
   long page_size=sysconf(_SC_PAGESIZE);
   return page_size>0 ? uint64_t(resident)*(unsigned long(page_size)/1024u) : 0;
}

static inline uint64_t frane_cpu_sample(bool queue)
{
   if (!frane_cpu_trace_path(queue)) return 0;
   static std::atomic<uint64_t> cb_seq {0}, q_seq {0};
   const uint64_t seq=(queue ? q_seq : cb_seq).fetch_add(1,std::memory_order_relaxed)+1;
   /* First 8 events, then one in every 32. No work when paths unset. */
   return seq<=8 || ((seq&31u)==0 && seq<=4000000ull) ? seq : 0;
}

struct frane_cpu_csv_writer {
   static constexpr unsigned N=16;
   std::mutex mutex;
   const char *path;
   const char *header;
   FILE *file=nullptr;
   bool failed=false;
   unsigned used=0;
   uint64_t last_flush_ns=0;
   char lines[N][384] {};
   frane_cpu_csv_writer(const char *p,const char *h):path(p),header(h) {}

   void flush_locked()
   {
      if (failed || !used) return;
      if (!file) {
         file=std::fopen(path,"a");
         if (!file) { failed=true; used=0; return; }
         struct stat st {};
         if (fstat(fileno(file),&st)==0 && st.st_size==0)
            std::fputs(header,file);
      }
      for (unsigned i=0;i<used;i++) std::fputs(lines[i],file);
      if (std::fflush(file)!=0) failed=true;
      used=0;
      last_flush_ns=frane_cpu_clock_ns(CLOCK_MONOTONIC);
   }

   void append(const char *line)
   {
      std::lock_guard<std::mutex> lock(mutex);
      if (failed) return;
      std::snprintf(lines[used],sizeof(lines[used]),"%s",line);
      ++used;
      const uint64_t now=frane_cpu_clock_ns(CLOCK_MONOTONIC);
      if (!last_flush_ns) last_flush_ns=now;
      if (used==N || (now>=last_flush_ns &&
          now-last_flush_ns>=2000000000ull))
         flush_locked();
   }
   ~frane_cpu_csv_writer() {
      std::lock_guard<std::mutex> lock(mutex);
      flush_locked();
      if (file) std::fclose(file);
   }
};

static inline void
frane_cpu_record_cb(uint64_t seq, uint64_t start_wall_ns,
                    uint64_t start_thread_ns, pthread_t begin_thread,
                    unsigned renderpasses, unsigned dispatches,
                    unsigned cs_entries, int result)
{
   const char *path=frane_cpu_trace_path(false);
   if (!path || !seq) return;
   const uint64_t mono=frane_cpu_clock_ns(CLOCK_MONOTONIC);
   const bool same=pthread_equal(begin_thread,pthread_self())!=0;
   const uint64_t cpu=same ? frane_cpu_clock_ns(CLOCK_THREAD_CPUTIME_ID) : 0;
   char row[384];
   std::snprintf(row,sizeof(row),
      "1,%llu,%llu,%llu,%llu,%u,%u,%u,%u,%d,%llu\n",
      (unsigned long long)seq,(unsigned long long)mono,
      (unsigned long long)frane_cpu_elapsed_us(start_wall_ns,mono),
      (unsigned long long)(same ? frane_cpu_elapsed_us(start_thread_ns,cpu) : 0),
      unsigned(same),renderpasses,dispatches,cs_entries,result,
      (unsigned long long)frane_cpu_rss_kib());
   static frane_cpu_csv_writer writer(path,
      "v,seq,mono_end_ns,record_wall_us,record_thread_cpu_us,"
      "same_thread,renderpasses,dispatches,cmdstream_entries,"
      "vk_result,process_rss_kib\n");
   writer.append(row);
}

static inline void
frane_cpu_record_queue(uint64_t seq,uint64_t enter_ns,
                       uint64_t enter_thread_ns,uint64_t lock_begin_ns,
                       uint64_t lock_acquired_ns,uint64_t driver_begin_ns,
                       uint64_t driver_end_ns,uint64_t exit_ns,
                       unsigned command_buffers,unsigned cmdstream_entries,
                       int result)
{
   const char *path=frane_cpu_trace_path(true);
   if (!path || !seq) return;
   const uint64_t cpu=frane_cpu_clock_ns(CLOCK_THREAD_CPUTIME_ID);
   char row[384];
   std::snprintf(row,sizeof(row),
      "1,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%u,%u,%d,%llu\n",
      (unsigned long long)seq,(unsigned long long)exit_ns,
      (unsigned long long)frane_cpu_elapsed_us(enter_ns,exit_ns),
      (unsigned long long)frane_cpu_elapsed_us(enter_thread_ns,cpu),
      (unsigned long long)frane_cpu_elapsed_us(lock_begin_ns,lock_acquired_ns),
      (unsigned long long)frane_cpu_elapsed_us(lock_acquired_ns,driver_begin_ns),
      (unsigned long long)frane_cpu_elapsed_us(driver_begin_ns,driver_end_ns),
      (unsigned long long)frane_cpu_elapsed_us(driver_end_ns,exit_ns),
      command_buffers,cmdstream_entries,result,
      (unsigned long long)frane_cpu_rss_kib());
   static frane_cpu_csv_writer writer(path,
      "v,seq,mono_end_ns,queue_wall_us,queue_thread_cpu_us,"
      "mutex_wait_us,driver_prepare_us,kernel_submit_call_us,"
      "after_submit_us,command_buffers,cmdstream_entries,"
      "vk_result,process_rss_kib\n");
   writer.append(row);
}
#endif
