#include "frane_a830_rfc7.h"
#include <cassert>
#include <climits>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <sstream>
int main()
{
   const char *path="/tmp/a830_rfc7_ci.csv";
   std::remove(path);
   assert(setenv("TU_FRANE_A830_RFC7_PATH",path,1)==0);
   assert(frane_a830_rfc7_path()!=nullptr);
   assert(frane_a830_rfc7_sat_mul(800u,4u)==3200u);
   assert(frane_a830_rfc7_sat_mul(UINT64_MAX,2u)==UINT64_MAX);
   {
      frane_a830_rfc7_sink sink;
      frane_a830_rfc7_row r{};
      r.rp_hash=0xabc;
      r.occurrence=1;
      r.pass_pixels=1280u*720u;
      r.tile_pixels=1280u*256u;
      r.tiles=3;
      r.drawcalls=120;
      r.attachments=2;
      r.load_cpp=4;
      r.store_cpp=4;
      r.clear_cpp=0;
      r.resolve_cpp=8;
      r.draw_bw_sample_sum=9344;
      r.sys_cpp=8;
      r.gmem_cpp=4;
      r.physical_gmem_bytes=8u*1024u*1024u;
      r.usable_gmem_bytes=6u*1024u*1024u;
      sink.write(r,path);
      frane_a830_rfc7_row timing{};
      timing.timing=true;
      timing.rp_hash=0xabc;
      timing.occurrence=1;
      timing.measure=true;
      timing.gpu_ticks=19200;
      timing.render_ticks=17000;
      timing.binning_ticks=2200;
      timing.max_tile_ticks=9000;
      timing.has_tile_ticks=true;
      sink.write(timing,path);
   }
   FILE *f=std::fopen(path,"r"); assert(f);
   char line[4096]={};
   assert(std::fgets(line,sizeof(line),f));
   std::string header(line);
   assert(header.find("est_store_bytes")!=std::string::npos);
   assert(header.find("binning_ticks")!=std::string::npos);
   assert(header.find("gpu_ticks")!=std::string::npos);
   assert(header.find("draw_bw_per_sample_sum")!=std::string::npos);
   assert(std::fgets(line,sizeof(line),f));
   std::string decision(line);
   assert(decision.find(",DECISION,0000000000000abc,1,GMEM,0")!=std::string::npos);
   assert(decision.find(",3686400,3686400,0,7372800,")!=std::string::npos);
   assert(std::fgets(line,sizeof(line),f));
   std::string measured(line);
   assert(measured.find(",TIMING,0000000000000abc,1,GMEM,1")!=std::string::npos);
   assert(measured.find(",19200,17000,2200,9000,1,0,0")!=std::string::npos);
   assert(!std::fgets(line,sizeof(line),f));
   std::fclose(f);
   auto columns=[](const std::string &s) {
      size_t count=1;
      for(char c:s)if(c==',')count++;
      return count;
   };
   assert(columns(header)==columns(decision));
   assert(columns(header)==columns(measured));
   std::remove(path);
   std::puts("RFC7 actual buffered CSV, units, session, estimate, timing and schema PASS");
}
