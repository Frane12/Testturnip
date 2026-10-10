#include "frane_a830_rfc2.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

int main()
{
   const char *path="/tmp/a830_rfc2_ci.csv";
   std::remove(path);
   assert(setenv("TU_FRANE_A830_RFC2_TRACE_PATH",path,1)==0);
   assert(frane_a830_rfc2_trace_path()!=nullptr);
   assert(std::strcmp(frane_a830_rfc2_reason_str(
      FRANE_A830_RFC2_BW2_ROLLBACK),"BW2_ROLLBACK")==0);
   frane_26318_smart_gmem_input in{};
   in.layout.pass_pixels=1280u*720u;
   in.layout.drawcalls=90;
   in.layout.usable_gmem=8u*1024u*1024u;
   in.selected_tile_pixels=1280u*240u;
   in.allocator_capacity_pixels=1280u*256u;
   in.sysmem_bandwidth_per_pixel=24;
   in.gmem_bandwidth_per_pixel=8;
   in.peak_live_cpp=8;
   in.peak_live_planes=3;
   in.a830_history_score=-5;
   in.a830_history_pairs=16;
   in.a830_rfc_has_cache=true;
   in.a830_rfc_cached_bw2.valid=true;
   in.a830_rfc_cached_bw2.score_delta=-18;

   frane_a830_rfc2_decision(0xabc,1,in,
      FRANE_A830_RFC2_BW2_ROLLBACK,true,true);
   frane_a830_rfc2_timing(0xabc,1,true,2500000,2500000,1900000,2,4,-7,16);
   frane_a830_rfc2_decision(0xabc,2,in,
      FRANE_A830_RFC2_PROFILED,false,false); // sampled out
   frane_a830_rfc2_timing(0xabc,2,false,1800000,2500000,1850000,2,5,-6,17); // sampled out

   FILE *f=std::fopen(path,"r");assert(f);
   char row[2048]{};
   assert(std::fgets(row,sizeof(row),f));
   assert(std::strstr(row,"gpu_ticks") && std::strstr(row,"source"));
   assert(std::fgets(row,sizeof(row),f));
   assert(std::strstr(row,"DECISION") && std::strstr(row,"BW2_ROLLBACK"));
   assert(std::strstr(row,"0000000000000abc") && std::strstr(row,",SYSMEM,1"));
   assert(std::fgets(row,sizeof(row),f));
   assert(std::strstr(row,"TIMING") && std::strstr(row,"2500000"));
   assert(std::strstr(row,"0000000000000abc") && std::strstr(row,",SYSMEM,1"));
   assert(std::fgets(row,sizeof(row),f)==nullptr);
   std::fclose(f);
   std::remove(path);
   std::puts("RFC2 actual native CSV decision/timing event write+join host PASS");
}
