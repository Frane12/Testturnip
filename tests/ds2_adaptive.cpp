#include <cassert>
#include <cstdio>
#include <chrono>
#include <initializer_list>
#include "frane_smart_adaptive.h"

static void pair(frane_adaptive_state &s, uint64_t g, uint64_t y,
                 uint32_t n, uint32_t draws=96) {
   frane_adaptive_feed(s,false,g,n,draws,9600);
   frane_adaptive_feed(s,true,y,n+1,draws,9600);
}

struct result { uint32_t adapted=0, measured=0, losers=0;uint64_t cost=0; };
static result reversal(bool adaptive, bool risk, uint64_t hash,
                       uint32_t feedback_delay=0) {
   frane_adaptive_state a{};frane_26364_state old{};result r{};
   struct pending {bool valid=false,sys=false;uint64_t duration=0;uint32_t n=0;} queue[32]{};
   for(uint32_t i=1;i<=8192+feedback_delay;++i) {
      auto &p=queue[i&31];
      if(p.valid) {
         if(adaptive) frane_adaptive_feed(a,p.sys,p.duration,p.n,192,9600);
         else frane_26364_feed(old,p.sys,p.duration,p.n);
         p.valid=false;
      }
      if(i>8192)continue;
      auto d=adaptive ? frane_adaptive_select(true,risk,frane_adaptive_pack(a),50,i,hash,192) :
         frane_26364_select(true,risk,frane_26364_pack(old),50,i,hash);
      const bool sys=d.owns ? d.sysmem : bool(i&1);
      const bool measure=d.owns ? d.measure : true;
      const uint64_t duration=i<4096 ? (sys?18000:10000) : (sys?10000:24000);
      r.cost+=duration;
      if(i>4096 && !r.adapted && (adaptive?a.votes.hist.preference:old.hist.preference)==FRANE_HIST_PREF_SYSMEM &&
         (adaptive?a.votes.hist.observations>=4:old.hist.confidence>=6))r.adapted=i;
      if(measure) {
         ++r.measured;
         if(feedback_delay) queue[(i+feedback_delay)&31]={true,sys,duration,i};
         else if(adaptive) frane_adaptive_feed(a,sys,duration,i,192,9600);
         else frane_26364_feed(old,sys,duration,i);
      }
      if(i>512&&i<4096&&sys)++r.losers;
   }
   return r;
}
int main() {
   static_assert(sizeof(frane_adaptive_state)<=192);
   assert(frane_adaptive_bank(63)==0 && frane_adaptive_bank(64)==1);
   assert(frane_adaptive_bank(255)==1 && frane_adaptive_bank(256)==2);
   assert(frane_adaptive_bank(1023)==2 && frane_adaptive_bank(1024)==3);
   assert(frane_adaptive_bank(UINT32_MAX)==3);
   assert(frane_adaptive_draw_code(UINT32_MAX)==16383);
   assert(!frane_adaptive_draws_close(10,UINT32_MAX));
   frane_adaptive_state s{};
   for(unsigned i=0;i<16;++i) pair(s,10000,18000,8*i);
   assert(s.votes.hist.preference==FRANE_HIST_PREF_GMEM&&s.votes.hist.confidence==8);
   for(uint64_t hash:{UINT64_C(0),UINT64_C(7),UINT64_MAX}) {
      for(bool risk:{false,true}) {
         auto w=frane_adaptive_pack(s);unsigned m=0,loser=0;
         for(uint32_t i=128;i<384;++i) {
            auto d=frane_adaptive_select(true,risk,w,100,i,hash,96);
            assert(d.owns&&d.tier==3);m+=d.measure;loser+=d.sysmem;
         }
         assert(loser==(risk?4:2));assert(m<=24);
      }
   }
   auto expired=frane_adaptive_select(true,false,frane_adaptive_pack(s),50,1000,0,96);
   assert(expired.owns&&expired.tier==0);
   assert(!frane_adaptive_select(false,true,UINT64_MAX,100,1,0,96).owns);
   frane_adaptive_state mismatch{};
   frane_adaptive_feed(mismatch,false,10000,1,65,9600);
   frane_adaptive_feed(mismatch,true,18000,2,250,9600);
   assert(mismatch.votes.hist.observations==0);
   frane_adaptive_feed(mismatch,false,10000,3,245,9600);
   assert(mismatch.votes.hist.observations==1);
   frane_adaptive_state distant{};
   frane_adaptive_feed(distant,false,10000,1,96,9600);
   frane_adaptive_feed(distant,true,18000,100,96,9600);
   assert(distant.votes.hist.observations==0);
   frane_adaptive_feed(distant,false,10000,101,96,9600);
   assert(distant.votes.hist.observations==1);
   frane_adaptive_state reverse{};
   frane_adaptive_feed(reverse,true,18000,0,96,9600);
   frane_adaptive_feed(reverse,false,10000,UINT32_MAX,96,9600);
   assert(reverse.votes.hist.observations==1&&reverse.votes.last_pair==0);
   frane_adaptive_state tie{};
   for(unsigned i=0;i<16;++i)pair(tie,10000,10000,8*i);
   unsigned tied_m=0;
   for(unsigned i=128;i<384;++i)tied_m+=frane_adaptive_select(true,false,frane_adaptive_pack(tie),50,i,19,96).measure;
   assert(tied_m<=24);
   auto spike=s;
   frane_adaptive_feed(spike,false,24000,140,96,9600);assert(!spike.burst_pairs);
   frane_adaptive_feed(spike,false,24000,156,96,9600);assert(spike.burst_pairs==4);
   auto changed=frane_adaptive_select(true,false,frane_adaptive_pack(s),50,130,0,224);
   assert(changed.tier==1);
   auto expensive=s;
   for(unsigned i=0;i<16;++i)pair(expensive,10000,50000,160+8*i);
   assert(expensive.expensive);
   unsigned loser=0;
   for(unsigned i=288;i<544;++i)loser+=frane_adaptive_select(true,true,frane_adaptive_pack(expensive),50,i,0,96).sysmem;
   assert(loser==1);
   unsigned cases=0;
   for(unsigned conf=0;conf<=8;++conf)for(unsigned count=0;count<=64;++count)
   for(unsigned age:{0u,8u,512u,513u,UINT32_MAX})for(bool risk:{false,true})
   for(int pref:{-1,0,1})for(uint32_t probability:{0u,50u,100u,UINT32_MAX}) {
      frane_adaptive_state q{};q.votes.hist.confidence=conf;q.votes.hist.preference=pref;
      q.votes.hist.bins[pref<0?0:pref>0?6:3]=count;q.votes.last_pair=100;
      auto d=frane_adaptive_select(true,risk,frane_adaptive_pack(q),probability,100+age,7,96);
      assert(d.owns);
      if(d.tier) {assert(pref&&conf>=4&&count>=(risk?4u:2u)&&age<=512);}
      ++cases;
   }
   uint32_t max_adapt=0;uint64_t new_cost=0,old_cost=0;
   for(uint64_t hash=0;hash<128;++hash)for(bool risk:{false,true})for(uint32_t delay:{0u,3u,7u}) {
      auto a=reversal(true,risk,hash,delay),b=reversal(false,risk,hash,delay);
      assert(a.adapted&&b.adapted);
      assert(a.adapted-4096<128);
      assert(a.measured<1200&&a.losers<70);
      if(a.adapted-4096>max_adapt)max_adapt=a.adapted-4096;
      new_cost+=a.cost;old_cost+=b.cost;
   }
   assert(new_cost<old_cost);
   frane_adaptive_state banks[4]{};uint32_t tickets[4]{};unsigned wrong=0;
   for(uint32_t i=0;i<8192;++i) {
      const uint32_t draws=i&1?600:48;const unsigned bank=frane_adaptive_bank(draws);
      auto d=frane_adaptive_select(true,true,frane_adaptive_pack(banks[bank]),50,++tickets[bank],33,draws);
      const bool wanted=bank==2;
      if(i>512&&d.sysmem!=wanted)++wrong;
      if(d.measure)frane_adaptive_feed(banks[bank],d.sysmem,d.sysmem==wanted?10000:18000,tickets[bank],draws,9600);
   }
   assert(wrong<160);
   auto huge=s;pair(huge,UINT64_MAX/2,UINT64_MAX,300);
   assert(huge.votes.cost[0] && huge.votes.cost[1]);
   frane_26358_mode_stats variance{};variance.mean=10000;variance.tail=20000;variance.samples=8;
   assert(frane_adaptive_cost(10000,variance)==12500);
   variance.mean=UINT64_MAX/2;variance.tail=UINT64_MAX;
   assert(frane_adaptive_cost(UINT64_MAX,variance)==UINT64_MAX);
   auto noisy=tie;noisy.stats[0]={10000,18000,16};noisy.stats[1]={11000,11000,16};
   auto quiet=frane_adaptive_select(true,true,frane_adaptive_pack(noisy),0,150,19,96);
   assert(quiet.sysmem);
   auto zero=s;auto before=frane_adaptive_pack(zero);frane_adaptive_feed(zero,false,0,200,96,9600);assert(before==frane_adaptive_pack(zero));
   volatile uint64_t checksum=0;
   const auto begin=std::chrono::steady_clock::now();
   for(uint32_t i=1;i<=1000000;++i) {
      auto d=frane_adaptive_select(true,i&1,frane_adaptive_pack(s),50,128+(i&127),i,96);
      checksum=checksum+d.sysmem+d.measure+d.tier;
   }
   const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-begin).count();
   std::printf("PASS: %u adaptive boundaries; 768 abrupt-change simulations; maximum adaptation %u occurrences; model total cost new=%llu old=%llu; isolated load banks, delayed feedback, stale/mismatched pairs, ties, spikes, expensive probes, rollover, saturation; host %.2f ns/call checksum=%llu\n",cases,max_adapt,(unsigned long long)new_cost,(unsigned long long)old_cost,double(ns)/1e6,(unsigned long long)checksum);
}
