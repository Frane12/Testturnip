#include <initializer_list>
#include <cassert>
#include <cstdio>
#include "frane_mesa_26364_a810_smart_v2.h"
static void pair(frane_26364_state &s,uint64_t g,uint64_t y,uint32_t n) {frane_26364_feed(s,false,g,n);frane_26364_feed(s,true,y,n+1);}
int main() {
 unsigned checked=0;
 for(bool sys: {false,true}) for(uint64_t hash: {UINT64_C(0),UINT64_C(91),UINT64_MAX}) for(uint32_t start: {0u,512u,UINT32_MAX-511u}) {
  frane_26364_state s{};for(unsigned i=0;i<32;i++)pair(s,sys?200:100,sys?100:200,i*8);
  s.last_pair=start;auto word=frane_26364_pack(s);assert(word&(UINT64_C(1)<<13));
  unsigned probes=0,losers=0,oldprobes=0,riskprobes=0;
  for(uint32_t i=0;i<512;i++) {
   auto d=frane_26364_select(true,false,word,50,start+i,hash);
   assert(d.owns&&d.tier==3);probes+=d.measure;losers+=d.sysmem!=sys;
   oldprobes+=frane_26364_select(true,false,word,50,start+i,hash,false).measure;
   riskprobes+=frane_26364_select(true,true,word,50,start+i,hash).measure;
  }
  assert(probes==2&&losers==1&&oldprobes==4&&riskprobes==4);++checked;
  pair(s,100,100,start+512);assert(!(frane_26364_pack(s)&(UINT64_C(1)<<13)));
 }
 frane_26364_state s{};for(unsigned i=0;i<32;i++)pair(s,UINT64_MAX/2+1,UINT64_MAX,i*8);
 assert(s.costly_pairs==0); // exact <2x boundary without multiplication overflow
 unsigned max_delay=0,measurements=0;
 for(uint64_t hash=0;hash<256;hash++) {
  frane_26364_state st{};unsigned adapted=0;
  for(unsigned i=1;i<=10000;i++) {
   auto d=frane_26364_select(true,false,frane_26364_pack(st),50,i,hash);
   bool sys=d.owns?d.sysmem:bool(i&1);bool m=d.owns?d.measure:true;
   if(m){++measurements;frane_26364_feed(st,sys,i<4096?(sys?200:100):(sys?100:200),i);}
   if(i>=4096&&!adapted&&st.hist.preference==FRANE_HIST_PREF_SYSMEM&&st.hist.confidence>=6)adapted=i;
  }
  assert(adapted&&adapted<6144);if(adapted-4096>max_delay)max_delay=adapted-4096;
 }
 printf("PASS loss budget: %u cadence/rollover cases, 256 reversal simulations, max adaptation delay=%u occurrences, measurements=%u/2560000\n",checked,max_delay,measurements);
}
