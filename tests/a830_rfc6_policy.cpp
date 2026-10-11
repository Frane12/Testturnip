#include "frane_a830_rfc6.h"
#include <cassert>
#include <cstdio>
#include <cstdint>
#include <climits>
int main() {
   const uint64_t hash=UINT64_C(0x91cf847c0ac283b0);
   const uint32_t vol4=(3u<<16)|(4u<<8)|4u;
   const uint32_t vol6=(3u<<16)|(6u<<8)|6u;
   const uint32_t vol20=(3u<<16)|(20u<<8)|20u;
   auto d=[&](bool enabled,int score,unsigned pairs,unsigned sys_n,
              unsigned gm_n,uint64_t sys,uint64_t gm,uint32_t vol,
              unsigned occ,unsigned last_sys,unsigned last_gm) {
      return frane_a830_rfc6_select(enabled,true,score,pairs,sys_n,gm_n,
                                    sys,gm,vol,occ,hash,last_sys,last_gm);
   };
   assert(frane_a830_rfc6_required_margin(vol4,64)==6);
   assert(frane_a830_rfc6_required_margin(vol6,64)==7);
   assert(frane_a830_rfc6_required_margin(vol20,64)>=16);
   assert(frane_a830_rfc6_required_margin(0,64)==100);
   assert(frane_a830_rfc6_required_margin((3u<<16)|(40u<<8)|4u,64)==100);
   /* User's 91cf... RP: 1.5% measured gap << actual volatility.
    * Never let RFC5's structural HOT choice bypass uncertainty.
    */
   auto uncertain=d(true,-7,80,64,64,11276,11444,vol6,100,98,97);
   assert(!uncertain.accepted);
   assert(d(true,-7,80,64,64,11276,11444,vol6,100,98,97).margin_pct==7);
   /* Hot ~8.7% win with low volatility: trust and sample often. */
   auto hot=d(true,-7,80,64,64,10500,11500,vol6,100,98,97);
   assert(hot.accepted && hot.base.workload_class==FRANE_A830_RFC5_HOT_CLOSE);
   assert(hot.base.d.audit_log2==4 && hot.base.d.measure_log2==3);
   assert(hot.base.d.sysmem == !hot.base.d.audit);
   assert(!d(true,-7,80,64,64,10500,11500,vol20,100,98,97).accepted);
   assert(!d(true,-5,80,64,64,10500,11500,vol6,100,98,97).accepted);
   assert(!d(true,-7,80,64,64,10500,11500,0,100,98,97).accepted);
   assert(!d(true,-7,80,64,64,10500,11500,vol6,100,0,97).accepted);
   assert(!d(true,-7,80,64,64,10500,11500,vol6,100,98,0).accepted);
   assert(!d(true,-7,80,64,64,10500,11500,vol6,500,98,97).accepted);
   assert(!d(true,-7,80,64,64,10500,11500,vol6,100,101,97).accepted);
   assert(!d(false,-7,80,64,64,10500,11500,vol6,100,98,97).accepted);
   /* Strong measured wins in both directions, sparse probes in cheap
    * stable RPs only, and always audit the other mode periodically.
    */
   auto small=d(true,-7,96,64,64,500,900,vol4,100,98,97);
   assert(small.accepted && small.high_confidence);
   assert(small.base.d.audit_log2==7 && small.base.d.measure_log2==6);
   auto g=d(true,7,96,64,64,900,500,vol4,100,98,97);
   assert(g.accepted && g.high_confidence && g.base.d.sysmem == g.base.d.audit);
   /* Heavy passes remain instrumented: don't starve important samples. */
   auto heavy=d(true,-7,96,64,64,10000,20000,vol4,100,98,97);
   assert(heavy.accepted && heavy.high_confidence &&
          heavy.base.d.measure_log2!=6);
   /* Weak but supported advantage gets frequent probes rather than
    * blindly locking in the mode for many scene transitions.
    */
   auto near=d(true,-7,80,64,64,10400,11500,vol6,100,98,97);
   assert(near.accepted && !near.high_confidence);
   assert(near.base.d.audit_log2==4 && near.base.d.measure_log2==3);
   /* Strong resource ratios never overflow in cost comparisons. */
   auto big=d(true,-7,96,64,64,UINT64_MAX/3,UINT64_MAX,vol4,100,98,97);
   assert(big.accepted);
   unsigned audits=0,measure=0;
   for(unsigned i=256;i<512;i++){
      auto x=d(true,-7,96,64,64,500,900,vol4,i,i-1,i-1);
      assert(x.accepted);
      if(x.base.d.audit){audits++;assert(x.base.d.measure);}
      measure+=x.base.d.measure;
   }
   assert(audits==2 && measure>=4 && measure<=6);
   std::puts("RFC6 confidence margin / freshness / reversal / cost-aware sampling PASS");
}
