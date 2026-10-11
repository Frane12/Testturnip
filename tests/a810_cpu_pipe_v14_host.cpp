#include "frane_a810_cpu_pipeline_probe.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <string>
int main() {
   const char *q="/tmp/a810_v14_queue.csv";
   const char *cb="/tmp/a810_v14_cb.csv";
   std::remove(q); std::remove(cb);
   assert(setenv("TU_FRANE_CPU_QUEUE_TRACE_PATH",q,1)==0);
   assert(setenv("TU_FRANE_CPU_CB_TRACE_PATH",cb,1)==0);
   assert(frane_cpu_elapsed_us(1000,999)==0);
   assert(frane_cpu_elapsed_us(1000,10999)==9);
   assert(frane_cpu_clock_ns(CLOCK_MONOTONIC)>0);
   assert(frane_cpu_clock_ns(CLOCK_THREAD_CPUTIME_ID)>0);
   const auto s=frane_cpu_sample(true);
   assert(s==1);
   for (int i=0;i<16;i++)
      frane_cpu_record_queue(s+i,1000000,500000,1100000,
         1200000,1400000,1550000,1600000,2,7,0);
   std::ifstream f(q);
   assert(f.good());
   std::string head,line;
   assert(std::getline(f,head));
   assert(head.find("kernel_submit_call_us")!=std::string::npos);
   assert(head.find("process_rss_kib")!=std::string::npos);
   assert(std::getline(f,line));
   assert(line.find(",2,7,0,")!=std::string::npos);
   auto cs=frane_cpu_sample(false);
   assert(cs==1);
   const uint64_t t=frane_cpu_clock_ns(CLOCK_MONOTONIC);
   for (int i=0;i<16;i++)
      frane_cpu_record_cb(cs+i,t,t,pthread_self(),1,2,3,0);
   std::ifstream g(cb);
   assert(g.good());
   assert(std::getline(g,head));
   assert(head.find("same_thread")!=std::string::npos);
   assert(std::getline(g,line));
   assert(line.find(",1,2,3,0,")!=std::string::npos);
   std::puts("A810 v1.4 buffered CB/queue timing + RSS schema PASS");
}
