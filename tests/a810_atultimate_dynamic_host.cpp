// SPDX-License-Identifier: MIT
#include "frane_a810_atultimate_trace.h"
#include "frane_mesa_2633_a810_profile_turbo.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <fstream>
#include <unistd.h>

int main() {
   frane_s1at1_context_input x{};
   x.pass_pixels=522240;x.estimated_tiles=10;x.drawcalls=215;
   x.sysmem_bandwidth_per_pixel=0;x.gmem_bandwidth_per_pixel=16;
   x.occurrences=256;x.sysmem_probability=50;
   auto cat=frane_s1at1_catalog_for(x);
   assert(cat.signature);
   frane_s1at3_snapshot s{};
   s.signature=cat.signature;
   s.samples[0]=3;s.samples[1]=3;s.score=20;
   s.volatility=0;s.at7_saving_4us=180;s.at7_noise_q8=20;
   std::atomic<uint64_t> w{0};
   frane_atu_dyn_result r;
   // Phase must be stable over 3 observations, no immediate winner lock.
   r=frane_atu_dyn_step(w,x,s,true); assert(!r.used && !r.phase_switch);
   r=frane_atu_dyn_step(w,x,s,true); assert(!r.used && !r.phase_switch);
   r=frane_atu_dyn_step(w,x,s,true); assert(!r.used && r.phase_switch);
   r=frane_atu_dyn_step(w,x,s,true); assert(!r.used && r.state.votes==1);
   r=frane_atu_dyn_step(w,x,s,true); assert(r.used && r.winner_switch && !r.decision.select_sysmem);
   assert(r.state.cooldown==24);
   // Existing champion remains stable, then a contradictory challenger
   // cannot flip until dwell and repeated strong GPU confirmation.
   s.score=-20;
   for(unsigned i=0;i<24;i++){
      r=frane_atu_dyn_step(w,x,s,true);
      assert(!r.used && r.state.winner==1);
   }
   for(unsigned i=0;i<4;i++){
      r=frane_atu_dyn_step(w,x,s,true);
      assert(!r.used && r.state.winner==1);
   }
   r=frane_atu_dyn_step(w,x,s,true);
   assert(r.used && r.winner_switch && r.decision.select_sysmem && r.state.winner==2);
   // Source of truth invalidates if missing, stale or volatile.
   s.stale[0]=true;
   r=frane_atu_dyn_step(w,x,s,true);
   assert(!r.used);
   s.stale[0]=false;s.volatility=8;
   r=frane_atu_dyn_step(w,x,s,true);
   assert(!r.used);
   s.volatility=0;
   // Guard a winning history from AT4 forced exploration.
   r=frane_atu_dyn_step(w,x,s,false);
   assert(!r.used);
   // Category change resets learned winner only after three detections.
   x.drawcalls=6;x.estimated_tiles=2;
   auto changed=frane_s1at1_catalog_for(x);
   assert(changed.signature!=cat.signature);
   s.signature=changed.signature;
   r=frane_atu_dyn_step(w,x,s,true);assert(!r.phase_switch && !r.used);
   r=frane_atu_dyn_step(w,x,s,true);assert(!r.phase_switch && !r.used);
   r=frane_atu_dyn_step(w,x,s,true);assert(r.phase_switch && !r.used && r.state.winner==0);
   // Rollback uses call-site opt-out and does not even touch this state.
   assert(frane_atu_dyn_unpack(w.load()).active==changed.signature);
   // Demonstrate log serialization with extra dynamic state columns.
   const char *p="/tmp/atu-v2-log-test.csv";unlink(p);
   assert(setenv("TU_FRANE_ATU_CONTEXT_TRACE_PATH",p,1)==0);
   frane_atu_trace_row row{};
   row.hash=0xbeef;row.occurrence=1;row.signature=changed.signature;
   row.in=x;row.s=s;row.dynamic=r;
   std::atomic<uint64_t> slots[FRANE_AT3_ENTRIES]{};
   frane_atu_trace(row,slots);
   std::ifstream f(p);assert(f.good());std::string line,body;
   while(std::getline(f,line)) body+=line+"\n";
   assert(body.find("dyn_phase_switch")!=std::string::npos);
   assert(body.find("DECISION")!=std::string::npos);
   unlink(p);
   puts("ATUltimate V2 phase/winner hysteresis, 24-decision dwell, stale and AT4 probe, context CSV PASS");
}
