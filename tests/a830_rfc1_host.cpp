#include "frane_a830_rfc1.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>

int main() {
   const char *file="/tmp/a830_rfc1_ci_trace.csv";
   std::remove(file);
   assert(setenv("TU_FRANE_A830_TRACE_PATH",file,1)==0);
   frane_26318_smart_gmem_input in{};
   in.layout.pass_pixels=1280ull*720ull;
   in.layout.drawcalls=80;
   in.layout.usable_gmem=8u*1024u*1024u;
   in.selected_tile_pixels=1280u*240u;
   in.allocator_capacity_pixels=1280u*256u;
   in.peak_live_cpp=8;
   in.peak_live_planes=3;
   in.sysmem_bandwidth_per_pixel=32;
   in.gmem_bandwidth_per_pixel=16;
   in.a830_history_score=5;
   in.a830_history_pairs=18;
   in.a830_rfc_has_cache=true;
   in.a830_rfc_cached_bw2.valid=true;
   in.a830_rfc_cached_bw2.score_delta=7;
   auto h=frane_a830_rfc1_fingerprint(in);
   assert(h==frane_a830_rfc1_fingerprint(in));
   frane_a830_rfc1_trace(0x12345,1,in,false,true);
   in.a830_history_score=-5;
   assert(frane_a830_rfc1_fingerprint(in)==h); // dynamic history not structural
   in.layout.drawcalls=400;
   assert(frane_a830_rfc1_fingerprint(in)!=h);
   frane_a830_rfc1_trace(0x12345,65,in,true,false);
   FILE *f=std::fopen(file,"r");assert(f);
   char buf[1024]{};
   assert(std::fgets(buf,sizeof(buf),f) && std::strstr(buf,"context_sig"));
   assert(std::fgets(buf,sizeof(buf),f) && std::strstr(buf,",GMEM,1"));
   assert(std::fgets(buf,sizeof(buf),f) && std::strstr(buf,",SYSMEM,0"));
   assert(std::fgets(buf,sizeof(buf),f)==nullptr);
   std::fclose(f);
   std::remove(file);
   std::puts("A830 RFC1 fingerprint + real CSV write/read host test PASS");
}
