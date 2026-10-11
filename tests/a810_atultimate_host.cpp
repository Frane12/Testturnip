// SPDX-License-Identifier: MIT
// ATUltimate A810: actual C++ history policy and opt-in context CSV.
#include "frane_a810_atultimate_trace.h"
#include "frane_mesa_2633_a810_profile_turbo.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <unistd.h>
int main() {
   frane_s1at1_context_input in {};
   in.pass_pixels=522240;in.estimated_tiles=10;in.drawcalls=209;
   in.sysmem_bandwidth_per_pixel=0;in.gmem_bandwidth_per_pixel=16;
   in.occurrences=256;in.sysmem_probability=50;
   auto c=frane_s1at1_catalog_for(in);
   assert(c.signature);
   frane_s1at3_snapshot s {};
   s.signature=c.signature;s.samples[0]=4;s.samples[1]=4;
   s.score=+17;s.at7_saving_4us=110;s.at7_noise_q8=15;
   frane_s1at1_decision at4{}, prior{};
   prior.override_mode=true;prior.select_sysmem=true;
   prior.effective_sysmem_probability=85;
   bool blocked=false;
   auto a=frane_atu_protect_prior(in,s,at4,prior,&blocked);
   assert(!a.override_mode && blocked); // measured GMEM vs SYS-biased AT6
   s.score=-17;blocked=false;prior.effective_sysmem_probability=10;
   prior.select_sysmem=false;
   a=frane_atu_protect_prior(in,s,at4,prior,&blocked);
   assert(!a.override_mode && blocked); // measured SYS vs GMEM-biased AT6
   s.score=+17;prior.effective_sysmem_probability=50;
   blocked=false;a=frane_atu_protect_prior(in,s,at4,prior,&blocked);
   assert(a.override_mode && !blocked); // balanced prior preserved
   prior.effective_sysmem_probability=90;
   for(unsigned kind=0;kind<8;++kind) {
      auto old=s; auto x=in; auto probe=at4;
      if(kind==0)old.samples[0]=1;
      if(kind==1)old.at7_saving_4us=39;
      if(kind==2)old.at7_noise_q8=81;
      if(kind==3)old.volatility=4;
      if(kind==4)old.stale[0]=true;
      if(kind==5)old.signature^=1;
      if(kind==6)probe.force_measure=true;
      if(kind==7)probe.override_mode=true;
      blocked=false;a=frane_atu_protect_prior(x,old,probe,prior,&blocked);
      assert(a.override_mode && !blocked);
   }
   // Trace serialization is separate and never affects the selector.
   char file[]="/tmp/a810-atu-XXXXXX";
   const int fd=mkstemp(file);assert(fd>=0);close(fd);unlink(file);
   assert(setenv("TU_FRANE_ATU_CONTEXT_TRACE_PATH",file,1)==0);
   frane_atu_trace_row row {};
   row.hash=0x12345;row.occurrence=1;row.signature=c.signature;
   row.in=in;row.s=s;row.mode_sysmem=true;
   row.source="AT6_AT4BASE";row.prior_rejected=true;
   std::atomic<uint64_t> slots[FRANE_AT3_ENTRIES]{};
   frane_s1at3_state st{};st.signature=c.signature;
   st.score=18;st.mode[0].samples=3;st.mode[1].samples=4;
   st.mode[0].mean=40000;st.mode[1].mean=20000;
   slots[frane_s1at3_slot(c.signature)].store(frane_s1at3_pack(st,64));
   frane_atu_trace(row,slots);
   std::ifstream f(file);assert(f.is_open());
   std::string line,all;int lines=0;while(std::getline(f,line)){lines++;all+=line+"\n";}
   assert(lines==3);
   assert(all.find("CONTEXT_MISS")==std::string::npos);
   assert(all.find("PRIOR_CONFLICT_BLOCKED")!=std::string::npos);
   assert(all.find("TABLE_SNAPSHOT")!=std::string::npos);
   assert(all.find("AT6_AT4BASE")!=std::string::npos);
   unlink(file);
   std::puts("ATUltimate: balanced fallback, GPU-history guard, probes, stale/noise, CSV TABLE and decision PASS");
}
