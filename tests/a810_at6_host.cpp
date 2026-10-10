// SPDX-License-Identifier: MIT
// AT6 pure policy regression using real AT3/AT4/AT5 helper headers.
#include "frane_a810_at6.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

static uint64_t next(uint64_t &s) {
   s += UINT64_C(0x9e3779b97f4a7c15);
   uint64_t x=s;
   x=(x^(x>>30))*UINT64_C(0xbf58476d1ce4e5b9);
   x=(x^(x>>27))*UINT64_C(0x94d049bb133111eb);
   return x^(x>>31);
}

static frane_s1at1_context_input ctx(uint64_t px,uint64_t tiles,
                                     uint32_t sys,uint32_t gm)
{
   frane_s1at1_context_input i {};
   i.pass_pixels=px;
   i.estimated_tiles=tiles;
   i.drawcalls=48;
   i.occurrences=128;
   i.sysmem_probability=50;
   i.sysmem_bandwidth_per_pixel=sys;
   i.gmem_bandwidth_per_pixel=gm;
   return i;
}

static void prior(frane_s1at1_context_input in,
                  frane_at6_class klass,bool expect_sys)
{
   assert(frane_at6_classify(in)==klass);
   frane_s1at3_snapshot s {};
   s.signature=frane_s1at1_catalog_for(in).signature;
   s.samples[0]=1;s.samples[1]=1;
   uint64_t seed=9345;
   unsigned n=0,agree=0,probes=0;
   for(unsigned j=0;j<3000;j++) {
      const auto w=next(seed);
      const auto a4=frane_at4_decide(in,s,w);
      const auto a5=frane_at5_decide(in,s,w,a4);
      const auto a6=frane_at6_decide(in,s,w,a4,a5);
      assert(!a5.force_measure || a6.force_measure);
      if(a6.override_mode && !a6.force_measure) {
         ++n;agree+=a6.select_sysmem==expect_sys;
      }
      probes+=a6.force_measure;
   }
   std::fprintf(stderr, "AT6 host: class=%u eligible=%u prior_agree=%u probes=%u\\n",
                unsigned(klass), n, agree, probes);
   /* AT6 never suppresses AT5 forced samples; some classes enter
    * a cautious AT5 fallback for a sizable portion of decisions. */
   assert(n>100 && probes>0);
   assert(agree*100 > n*60);
}

int main()
{
   prior(ctx(522240,15,0,24),FRANE_AT6_SYSMEM_LOW_TRAFFIC,true);
   prior(ctx(522240,10,8,8),FRANE_AT6_GMEM_BALANCED_REUSE,false);
   prior(ctx(130560,4,12,16),FRANE_AT6_SYSMEM_TINY_PASS,true);
   prior(ctx(262144,3,4,4),FRANE_AT6_GMEM_MID_TILE,false);
   prior(ctx(522240,15,8,16),FRANE_AT6_SYSMEM_ASYMMETRIC,true);

   // AT4 fully trusted measured mode is authoritative, even against prior.
   auto in=ctx(522240,15,0,24);
   frane_s1at3_snapshot t {};
   t.signature=frane_s1at1_catalog_for(in).signature;
   t.samples[0]=16;t.samples[1]=16;t.score=16;
   uint64_t seed=45;
   for(unsigned j=0;j<10000;j++) {
      const auto w=next(seed);
      const auto a4=frane_at4_decide(in,t,w);
      const auto a5=frane_at5_decide(in,t,w,a4);
      const auto a6=frane_at6_decide(in,t,w,a4,a5);
      assert(a6.override_mode==a5.override_mode);
      assert(a6.select_sysmem==a5.select_sysmem);
      assert(a6.force_measure==a5.force_measure);
   }
   // Volatile or stale measurements cannot trigger AT6 class priors.
   for(int kind=0;kind<2;kind++){
      auto s=t;s.score=2;
      if(kind==0)s.stale[0]=true;
      else s.volatility=7;
      for(unsigned j=0;j<200;j++) {
         const auto w=next(seed);
         const auto a4=frane_at4_decide(in,s,w);
         const auto a5=frane_at5_decide(in,s,w,a4);
         const auto a6=frane_at6_decide(in,s,w,a4,a5);
         assert(a6.select_sysmem==a5.select_sysmem);
         assert(a6.force_measure==a5.force_measure);
      }
   }
   // Disallow unvalidated structural regimes.
   in=ctx(522240,30,0,24);
   assert(frane_at6_classify(in)==FRANE_AT6_UNCLASSIFIED);
   in=ctx(1048576,10,0,24);
   assert(frane_at6_classify(in)==FRANE_AT6_UNCLASSIFIED);
   std::puts("AT6 classified prior, exploratory samples, stale guard, AT4 trust PASS");
}
