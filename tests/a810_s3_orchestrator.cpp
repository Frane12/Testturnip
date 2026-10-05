#include <cassert>
#include <chrono>
#include <cstdio>
#include <initializer_list>
#include "frane_s3_orchestrator.h"
#include "frane_mesa_26364_a810_smart_v2.h"

static void pair(frane_s3_state &s,const frane_s3_config &c,
                 uint64_t g,uint64_t y,uint32_t tag) {
   frane_s3_feed(s,c,false,g,tag,true,tag);
   frane_s3_feed(s,c,true,y,tag+1,true,tag);
}

int main() {
   auto c=frane_s3_normalize(frane_s3_config{});
   frane_s3_state s {};
   for(uint32_t i=0;i<16;i++) pair(s,c,1000,2000,16*i);
   assert(s.trusted && !s.sysmem && s.mean==-500 && !s.deviation);
   for(uint64_t hash : {UINT64_C(0),UINT64_C(17),UINT64_MAX})
   for(uint32_t start : {0u,1024u,UINT32_MAX-1023u}) {
      auto t=s;t.stamp=start;
      for(uint32_t block=0;block<2;block++) {
         uint32_t pairs=0,measured=0,opponents=0;
         for(uint32_t i=0;i<512;i++) {
            auto d=frane_s3_select(c,false,frane_s3_pack(t,c),50,start+block*512+i,hash);
            assert(d.owns && d.tier==3);
            pairs+=d.paired; measured+=d.measure; opponents+=d.sysmem;
         }
         assert(pairs==2 && opponents==1 && measured>=2 && measured<=4);
      }
   }
   for(uint64_t hash : {UINT64_C(0),UINT64_C(99),UINT64_MAX}) {
      uint32_t requests=0;
      for(uint32_t i=0;i<16;i++) requests+=frane_s3_select(c,false,0,50,i,hash).measure;
      assert(requests==2);
   }
   auto off=c;off.enabled=false;
   assert(!frane_s3_select(off,false,frane_s3_pack(s,c),50,255,0).owns);
   off=c;off.policy=0;
   assert(!frane_s3_select(off,false,frane_s3_pack(s,c),50,255,0).owns);
   assert(frane_s3_select(c,false,frane_s3_pack(s,c),50,4000,0).tier==0);

   frane_s3_state reorder {};
   frane_s3_feed(reorder,c,true,2000,11,true,10);
   frane_s3_feed(reorder,c,false,1000,10,true,10);
   assert(reorder.pairs==1);
   frane_s3_feed(reorder,c,false,1000,10,true,10);
   frane_s3_feed(reorder,c,true,2000,11,true,10);
   assert(reorder.pairs==1);
   frane_s3_feed(reorder,c,false,1000,20,true,20);
   frane_s3_feed(reorder,c,true,2000,31,true,30);
   assert(reorder.pairs==1);
   frane_s3_feed(reorder,c,false,1000,30,true,30);
   assert(reorder.pairs==2);
   frane_s3_feed(reorder,c,true,2000,21,true,20);
   assert(reorder.pairs==2);
   frane_s3_state wrap {};
   pair(wrap,c,UINT64_MAX/2,UINT64_MAX,UINT32_MAX-1);
   pair(wrap,c,UINT64_MAX/2,UINT64_MAX,2);
   assert(wrap.pairs==2 && wrap.mean<0);
   assert(frane_s3_average(UINT64_MAX-3,UINT64_MAX,1)==UINT64_MAX-2);
   assert(frane_s3_ratio(UINT64_MAX,UINT64_MAX)==1000);

   frane_s3_state noise {};
   for(uint32_t i=0;i<200;i++) pair(noise,c,i&1?1000:1900,i&1?1900:1000,i*16);
   assert(!noise.trusted && noise.deviation>300);
   frane_s3_state tiny {};
   for(uint32_t i=0;i<16;i++) pair(tiny,c,20,40,i*16);
   assert(tiny.tiny && !tiny.trusted);

   auto drift=s;
   frane_s3_feed(drift,c,false,2000,300,false,0);
   assert(drift.trusted && drift.drift_count==1);
   frane_s3_feed(drift,c,false,2000,301,false,0);
   assert(!drift.trusted && drift.resets==1 && drift.pairs==0);
   pair(drift,c,1000,2000,298);
   assert(drift.pairs==0);
   for(uint32_t i=0;i<8;i++) pair(drift,c,2000,1000,320+i*16);
   assert(drift.trusted && drift.sysmem);

   auto bad=c;
   bad.cold_log2=UINT32_MAX;bad.warm_log2=0;bad.hot_log2=0;
   bad.min_pairs=0;bad.ema_shift=UINT32_MAX;bad.max_age=0;
   bad.max_tiles=UINT32_MAX;bad.risk=UINT32_MAX;bad.drift_hits=0;
   bad=frane_s3_normalize(bad);
   assert(bad.cold_log2==6 && bad.warm_log2>=6 && bad.hot_log2>=6 &&
          bad.min_pairs==4 && bad.ema_shift==5 && bad.max_age>=128 &&
          bad.max_tiles==128 && bad.risk==400 && bad.drift_hits==1);
   frane_2634_gmem_layout_input layout {};
   layout.physical_gmem=1048576;layout.usable_gmem=589824;
   layout.pixels_per_tile=30000;layout.pass_pixels=960*544;layout.drawcalls=100;
   assert(frane_s3_eligible(layout,c));
   layout.selected_tile_count=64;assert(frane_s3_eligible(layout,c));
   layout.selected_tile_count=65;assert(!frane_s3_eligible(layout,c));
   layout.selected_tile_count=4;layout.usable_gmem=layout.physical_gmem+1;
   assert(!frane_s3_eligible(layout,c));

   uint32_t total_measured=0,stable_measured=0,adapted=0;
   frane_s3_state sim {};
   for(uint32_t i=1;i<=50000;i++) {
      auto d=frane_s3_select(c,false,frane_s3_pack(sim,c),50,i,73);
      if(d.measure) {
         ++total_measured;if(i>5000 && i<25000)++stable_measured;
         uint64_t duration=i<25000 ? (d.sysmem?2000:1000) : (d.sysmem?1000:2000);
         frane_s3_feed(sim,c,d.sysmem,duration,i,d.paired,d.tag);
      }
      if(i>=25000 && !adapted && sim.trusted && sim.sysmem) adapted=i;
   }
   assert(stable_measured<200 && adapted>=25000 && adapted<26200);
   assert(total_measured<800);
   for(uint32_t n=0;n<10000;n++) {
      const uint32_t v=frane_s3_mix(n);
      auto f=c;f.cold_log2=v%20;f.hot_log2=(v>>4)%20;f.warm_log2=(v>>8)%20;
      f.sentinel_log2=(v>>12)%20;f.min_pairs=(v>>16)%24;
      f.risk=(v>>20)%800;f.ema_shift=(v>>24)%8;f=frane_s3_normalize(f);
      frane_s3_state st{};
      for(uint32_t j=0;j<40;j++) {
         const uint32_t occ=UINT32_MAX-500+j*8;
         pair(st,f,UINT64_MAX-(v|1),UINT64_MAX/2,occ);
         auto d=frane_s3_select(f,bool(n&1),frane_s3_pack(st,f),v%102,occ+2,v);
         assert(d.owns && st.mean>=-1000 && st.mean<=1000 && st.deviation>=0);
      }
   }
   volatile uint64_t checksum=0;
   const auto begin=std::chrono::steady_clock::now();
   for(uint32_t i=0;i<1000000;i++) {
      auto t=s;t.stamp=i-1;
      auto d=frane_s3_select(c,false,frane_s3_pack(t,c),50,i,17);
      checksum=checksum+d.sysmem+d.measure+d.tier;
   }
   const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now()-begin).count();
   printf("PASS S3: tagged pairs, reordering, duplicate rejection, rollover, overflow, noisy/tiny passes, drift, config bounds, layout bounds, 400000 fuzz pairs; stable measurements=%u/19999; reversal at %u; total=%u/50000; state=%zu bytes; host selector %.2f ns/call; checksum=%llu\n",
      stable_measured,adapted,total_measured,sizeof(frane_s3_state),double(ns)/1000000,
      (unsigned long long)checksum);
}
