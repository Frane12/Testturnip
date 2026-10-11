// SPDX-License-Identifier: MIT
#include "frane_a810_atultimate_trace.h"
#include "frane_mesa_2633_a810_profile_turbo.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <atomic>
#include <unistd.h>

static frane_s1at1_context_input make_ctx(unsigned tiles, unsigned draws) {
   frane_s1at1_context_input x {};
   x.pass_pixels=522240; x.estimated_tiles=tiles; x.drawcalls=draws;
   x.sysmem_bandwidth_per_pixel=0; x.gmem_bandwidth_per_pixel=16;
   x.occurrences=256; x.sysmem_probability=50;
   return x;
}
static frane_s1at3_snapshot measured(const frane_s1at1_context_input &x,
                                       int score) {
   frane_s1at3_snapshot s {};
   s.signature=frane_s1at1_catalog_for(x).signature;
   assert(s.signature);
   s.samples[0]=3;s.samples[1]=3;s.score=score;
   s.at7_saving_4us=170;s.at7_noise_q8=16;s.volatility=0;
   return s;
}
static frane_atu_v3_result step(
    std::atomic<uint64_t> cache[FRANE_ATU_V3_SLOTS],
    std::atomic<uint64_t> &phase,std::atomic<uint32_t> &counter,
    const frane_s1at1_context_input &x,
    const frane_s1at3_snapshot &s, bool allow=true,
    bool probe=false, bool runtime=false) {
   return frane_atu_v3_step(cache,phase,counter,x,s,allow,
                            probe,runtime,true,3,24);
}
static int commas(const std::string &s) {
   int n=0;for(char c:s)if(c==',')++n;return n;
}

int main() {
   std::atomic<uint64_t> slots[FRANE_ATU_V3_SLOTS]{};
   std::atomic<uint64_t> phase{0};
   std::atomic<uint32_t> seq{0};
   auto a=make_ctx(10,215),b=make_ctx(2,6);
   auto aa=measured(a,+20),bb=measured(b,-20);
   assert(aa.signature!=bb.signature);
   // Unknown category requires 3 observations; >=2 strong votes acquire.
   auto r=step(slots,phase,seq,a,aa);
   assert(r.why==ATU_V3_PHASE_WAIT && !r.used);
   r=step(slots,phase,seq,a,aa);
   assert(!r.used);
   r=step(slots,phase,seq,a,aa);
   assert(r.phase_switched && r.used && !r.decision.select_sysmem);
   assert(r.winner_acquired || r.slot.winner==1);
   const unsigned a_slot=r.slot_id;
   assert(r.slot.frequency>=3);
   // Two observations to return to known category, winner already cached.
   step(slots,phase,seq,b,bb);
   step(slots,phase,seq,b,bb);
   r=step(slots,phase,seq,b,bb);
   assert(r.used && r.decision.select_sysmem);
   const unsigned b_slot=r.slot_id;assert(b_slot!=a_slot);
   r=step(slots,phase,seq,a,aa);
   assert(!r.used && r.why==ATU_V3_PHASE_WAIT && r.cache_hit);
   r=step(slots,phase,seq,a,aa);
   assert(r.used && r.cache_hit && !r.decision.select_sysmem);
   assert(r.slot_id==a_slot);
   // AT4 probes preserve existing authority; cache still remains valid.
   r=step(slots,phase,seq,a,aa,false,true);
   assert(!r.used && r.why==ATU_V3_AT4_PROBE);
   r=step(slots,phase,seq,a,aa,false,false,true);
   assert(!r.used && r.why==ATU_V3_RUNTIME_PRIORITY);
   // Stale timestamps cannot resurrect cached champion.
   auto stale=aa;stale.stale[0]=true;
   r=step(slots,phase,seq,a,stale);
   assert(!r.used && r.why==ATU_V3_STALE_HISTORY);
   auto mismatch=aa; mismatch.signature ^= 1;
   r=step(slots,phase,seq,a,mismatch);
   assert(!r.used && r.why==ATU_V3_NO_HISTORY);
   // Opposite proof needs cooldown expiry AND consecutive directional votes.
   auto opposite=aa;opposite.score=-20;
   for(unsigned i=0;i<24;i++){
      r=step(slots,phase,seq,a,opposite);
      assert(!r.used && r.slot.winner==1);
   }
   // One contrary vote, then original score: no wrong-direction carryover.
   r=step(slots,phase,seq,a,opposite);
   assert(!r.used);
   r=step(slots,phase,seq,a,aa);
   assert(r.used && r.slot.winner==1 && r.slot.votes==0);
   for(unsigned i=0;i<4;i++){
      r=step(slots,phase,seq,a,opposite);
      assert(!r.used && r.slot.winner==1);
   }
   r=step(slots,phase,seq,a,opposite);
   assert(r.used && r.winner_changed && r.decision.select_sysmem);
   // No cross-context activation even when old samples incorrectly supplied.
   r=step(slots,phase,seq,b,aa);
   assert(!r.used);
   // CSV header and DECISION and TABLE columns must match exactly.
   const char *path="/tmp/atu-v3-trace-test.csv";unlink(path);
   assert(setenv("TU_FRANE_ATU_CONTEXT_TRACE_PATH",path,1)==0);
   frane_atu_trace_row row {};
   row.hash=1234;row.occurrence=1;row.signature=aa.signature;
   row.in=a;row.s=aa;row.v3=r;
   std::atomic<uint64_t> history[FRANE_AT3_ENTRIES]{};
   frane_s1at3_state st{};
   st.signature=aa.signature;
   st.mode[0].samples=3;st.mode[1].samples=3;
   st.mode[0].mean=800;st.mode[1].mean=450;
   history[frane_s1at3_slot(st.signature)].store(
      frane_s1at3_pack(st,16));
   frane_atu_trace(row,history);
   std::ifstream f(path);std::string header,dec,table;
   assert(std::getline(f,header)&&std::getline(f,dec)&&std::getline(f,table));
   assert(header.find("v3_reason")!=std::string::npos);
   assert(dec.find("DECISION")!=std::string::npos);
   assert(table.find("TABLE")!=std::string::npos);
   assert(commas(header)==commas(dec));
   assert(commas(header)==commas(table));
   unlink(path);
   puts("ATUltimate V3: 4-way cached champions, phase reentry, dwell, directional votes, AT4 priority, stale guards and CSV PASS");
}
