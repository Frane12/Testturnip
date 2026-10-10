#include "frane_a830_rfc4.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

int main() {
   uint32_t vol=0;
   assert(frane_a830_rfc4_error_pct(1000,1100)==10);
   assert(frane_a830_rfc4_error_pct(1000,500)==50);
   assert(frane_a830_rfc4_error_pct(0,1000)==100);
   assert(frane_a830_rfc4_error_pct(UINT64_MAX,0)==100);
   assert(frane_a830_rfc4_update_volatility(0,true,100,100,2)==0);
   vol=frane_a830_rfc4_update_volatility(vol,true,1000,1020,3);
   assert((vol & (1u<<16))!=0 && (vol&255u)==2);
   vol=frane_a830_rfc4_update_volatility(vol,false,1000,1020,3);
   assert((vol & (1u<<17))!=0 && ((vol>>8)&255u)==2);
   const uint32_t stable_vol=vol;
   vol=frane_a830_rfc4_update_volatility(vol,true,1000,1500,40);
   assert((vol&255u)>2u); // adapt quickly to change

   const uint64_t hash=0x12a50ee34ull;
   auto d=[&](bool on,int score,unsigned pairs,unsigned sysN,unsigned gmN,
              uint64_t sys,uint64_t gm,uint32_t v,unsigned occ) {
      return frane_a830_rfc4_select(on,true,score,pairs,sysN,gmN,
                                     sys,gm,v,occ,hash);
   };
   assert(!d(false,-7,40,40,40,80,100,stable_vol,1).owns);
   assert(!d(true,-7,15,40,40,80,100,stable_vol,1).owns);
   assert(!d(true,-5,40,40,40,80,100,stable_vol,1).owns);
   assert(!d(true,-7,40,7,40,80,100,stable_vol,1).owns);
   assert(!d(true,-7,40,40,40,95,100,stable_vol,1).owns);
   assert(!d(true,7,40,40,40,120,110,stable_vol,1).owns);
   assert(!d(true,7,40,40,40,100,90,stable_vol,0).owns);

   const auto sys=d(true,-7,100,64,64,60,100,stable_vol,1);
   const auto gm=d(true,7,100,64,64,100,60,stable_vol,1);
   assert(sys.owns && sys.stable && sys.audit_log2==6 && sys.measure_log2==5);
   assert(gm.owns && gm.stable && gm.audit_log2==6 && gm.measure_log2==5);

   unsigned gma=0, gmmeasure=0, sysa=0;
   for(unsigned i=1;i<=4096;i++){
      auto x=d(true,-7,100,64,64,60,100,stable_vol,i);
      auto y=d(true,7,100,64,64,100,60,stable_vol,i);
      assert(x.owns && y.owns);
      assert(x.sysmem != x.audit);
      assert(y.sysmem == y.audit);
      if(x.audit){sysa++;assert(x.measure);}
      if(y.audit){gma++;assert(y.measure);}
      gmmeasure+=y.measure;
   }
   assert(sysa==64 && gma==64);
   assert(gmmeasure>=128 && gmmeasure<=192);

   /* Unstable RP returns to the original SMART learner; lower confidence
    * increases probes, but no allocations or HW state are changed.
    */
   uint32_t volatile_word=(1u<<16)|(1u<<17)|(40u<<8)|50u;
   assert(!d(true,-7,40,40,40,60,100,volatile_word,1).owns);
   const uint32_t moderate=(1u<<16)|(1u<<17)|(19u<<8)|18u;
   auto mid=d(true,-7,40,40,40,60,100,moderate,1);
   assert(mid.owns && !mid.stable && mid.audit_log2==5 && mid.measure_log2==4);
   assert(d(true,-7,40,40,40,60,100,0,1).owns);
   /* Tick ratio computations are overflow-safe. */
   assert(d(true,-7,40,40,40,UINT64_MAX/3,UINT64_MAX,moderate,1).owns);
   puts("RFC4 bidirectional adaptation / sampling / surprise / rollback PASS");
}
