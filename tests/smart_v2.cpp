#include <initializer_list>
#include <cassert>
#include <cstdio>
#include <chrono>
#include "frane_mesa_26364_a810_smart_v2.h"
static void pair(frane_26364_state &s, uint64_t g, uint64_t y, uint32_t n) {
 frane_26364_feed(s,false,g,n); frane_26364_feed(s,true,y,n+1);
}
int main() {
 frane_26364_state s{};
 for(unsigned i=0;i<16;i++) pair(s,100,200,i*8);
 assert(s.hist.confidence==8 && s.hist.preference==FRANE_HIST_PREF_GMEM);
 auto word=frane_26364_pack(s);
 // Exhaust exact cadence for many hash offsets and counter rollover.
 for(uint64_t hash: {UINT64_C(0),UINT64_C(123456),UINT64_MAX}) {
  for(uint32_t start: {0u,256u,UINT32_MAX-255u}) {
   frane_26364_state temp=s;temp.last_pair=start;word=frane_26364_pack(temp);
   unsigned measurements=0,losers=0;
   for(uint32_t i=0;i<256;i++) {
    auto d=frane_26364_select(true,false,word,20,start+i,hash);
    assert(d.owns && d.tier==3);measurements+=d.measure;losers+=d.sysmem;
   }
   assert(measurements==2 && losers==1);
  }
 }
 word=frane_26364_pack(s);
 assert(!frane_26364_select(false,false,word,20,130,0).owns);
 // Expired history must not own every recurrence.
 unsigned expired_owned=0;
 for(unsigned i=0;i<8;i++)expired_owned+=frane_26364_select(true,false,word,20,1024+i,0).owns;
 assert(expired_owned==2);
 // Old opposite sample cannot create a fresh vote or be reused.
 frane_26364_state stale{};
 frane_26364_feed(stale,false,100,1);frane_26364_feed(stale,true,200,500);
 assert(stale.hist.observations==0);
 frane_26364_feed(stale,false,100,501);assert(stale.hist.observations==1);
 frane_26364_feed(stale,false,100,502);assert(stale.hist.observations==1);
 // Completion order and wrap remain valid within the small pairing window.
 frane_26364_state reverse{};
 frane_26364_feed(reverse,true,200,10);frane_26364_feed(reverse,false,100,9);
 assert(reverse.hist.observations==1 && reverse.last_pair==10);
 pair(reverse,100,200,UINT32_MAX);assert(reverse.hist.observations==2);
 // Two fresh opposite pairs invalidate a well established winner.
 pair(s,200,100,200);assert(s.hist.confidence<8);
 pair(s,200,100,208);assert(s.hist.observations==1);
 for(unsigned i=0;i<16;i++)pair(s,200,100,216+i*8);
 assert(s.hist.preference==FRANE_HIST_PREF_SYSMEM && s.hist.confidence==8);
 // Ties dilute confidence; six wins plus many ties cannot lock a scene.
 frane_26364_state ties{};
 for(unsigned i=0;i<6;i++)pair(ties,100,200,8*i);
 for(unsigned i=6;i<20;i++)pair(ties,100,100,8*i);
 assert(ties.hist.confidence<4);
 // Lifetime counters and UINT64_MAX inputs keep working after saturation.
 frane_26364_state saturated{};saturated.hist.observations=UINT32_MAX;
 for(unsigned i=0;i<100000;i++)pair(saturated,UINT64_MAX/2,UINT64_MAX,i*8);
 assert(saturated.hist.observations==UINT32_MAX && saturated.hist.confidence==8);
 assert(frane_26362_recent_total(saturated.hist)<=64);
 // Warm evidence is insufficient for structural tail-risk passes.
 frane_26364_state warm{};for(unsigned i=0;i<8;i++)pair(warm,100,200,i*8);
 auto d=frane_26364_select(true,true,frane_26364_pack(warm),20,59,0);
 assert(d.tier==0);
 // Regime simulation: selector and submit feedback, abrupt reversal at 4096.
 frane_26364_state sim{};unsigned measured=0,locked_hits=0,adapted=0;
 for(uint32_t i=1;i<=10000;i++) {
  auto dec=frane_26364_select(true,false,frane_26364_pack(sim),50,i,0);
  bool sys=dec.owns ? dec.sysmem : bool(i&1);
  bool measure=dec.owns ? dec.measure : true; // conservative S1 cold model
  if(measure) {++measured;frane_26364_feed(sim,sys,i<4096?(sys?200:100):(sys?100:200),i);}
  if(i>300 && i<4096 && dec.tier==3)++locked_hits;
  if(i>4096 && !adapted && sim.hist.preference==FRANE_HIST_PREF_SYSMEM && sim.hist.confidence>=6)adapted=i;
 }
 assert(locked_hits>3000 && adapted && adapted<5000);
 // Exhaust policy boundaries: probabilities, sample thresholds, tail-risk,
 // instability, confidence. Owned warm/hot hits always honor tier rules.
 unsigned cases=0;
 for(unsigned c=0;c<=8;c++) for(unsigned n=0;n<=64;n++)
 for(unsigned flips: {0u,4u,8u}) for(unsigned p=0;p<=101;p++)
 for(bool risk: {false,true}) for(int pref: {-1,1}) {
  frane_26364_state st{};st.hist.confidence=c;st.hist.preference=pref;
  st.hist.bins[pref<0?0:6]=n;st.hist.switches=flips;st.last_pair=100;
  auto q=frane_26364_select(true,risk,frane_26364_pack(st),p,101,19);
  if(q.tier){assert(q.owns);assert(n>=8&&c>=4);if(risk)assert(q.tier>=2);}
  assert(!frane_26364_select(false,risk,frane_26364_pack(st),p,101,19).owns);
  ++cases;
 }
 assert(cases==716040);
 // Jitter moves the probe slot between periods, including both parities.
 unsigned even=0,odd=0; uint32_t previous=UINT32_MAX;unsigned moves=0;
 for(uint32_t block=0;block<128;block++) {
  frane_26364_state st=sim;st.last_pair=block*256;
  unsigned hits=0;uint32_t first=0;
  for(uint32_t j=0;j<256;j++){
   auto q=frane_26364_select(true,false,frane_26364_pack(st),50,block*256+j,91);
   if(q.measure){if(!hits)first=j;++hits;}
  }
  assert(hits==2);(first&1)?++odd:++even;
  moves+=previous!=first;previous=first;
 }
 assert(even>30 && odd>30 && moves>100);
 // Host throughput check uses varied packed words to avoid constant folding.
 volatile uint64_t checksum=0;
 const auto begin=std::chrono::steady_clock::now();
 for(uint32_t i=1;i<=1000000;i++){
  frane_26364_state t=sim;t.last_pair=i-1;
  auto dec=frane_26364_select(true,false,frane_26364_pack(t),50,i,17);
  checksum=checksum+dec.sysmem+dec.measure+dec.tier;
 }
 const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-begin).count();
 printf("PASS: cadence, expiration, fresh pairs, rollover, ties, saturation, reversal; simulated adaptation occurrence=%u, measurements=%u/10000; host helper %.2f ns/call, checksum=%llu\n",adapted,measured,double(ns)/1e6,(unsigned long long)checksum);
}
