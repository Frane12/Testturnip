#include "frane_a830_rfc5.h"
#include <cassert>
#include <cstdint>
#include <cstdio>
int main()
{
   const uint64_t hash=UINT64_C(0xf49817c5);
   const uint32_t stable=(3u<<16)|(6u<<8)|6u;
   auto d=[&](bool enabled,int score,unsigned pairs,unsigned sysN,
              unsigned gmN,uint64_t sys,uint64_t gm,uint32_t vol,
              unsigned occ) {
      return frane_a830_rfc5_select(enabled,true,score,pairs,sysN,gmN,
                                    sys,gm,vol,occ,hash);
   };
   /* Real user log: GPU-hot pass ~0.6ms with only 5-10% advantage.
    * RFC4 threshold (>=10%) does not own, RFC5 with stronger evidence does.
    */
   auto hot=d(true,-7,64,48,48,10500,11500,stable,1);
   assert(hot.d.owns && hot.workload_class==FRANE_A830_RFC5_HOT_CLOSE);
   assert(hot.d.audit_log2==4 && hot.d.measure_log2==3);
   assert(!d(false,-7,64,48,48,10500,11500,stable,1).d.owns);
   assert(!d(true,-5,64,48,48,10500,11500,stable,1).d.owns);
   assert(!d(true,-7,31,48,48,10500,11500,stable,1).d.owns);
   assert(!d(true,-7,64,23,48,10500,11500,stable,1).d.owns);
   assert(!d(true,-7,64,48,48,10500,11500,0,1).d.owns);
   assert(!d(true,-7,64,48,48,10500,11500,(3u<<16)|(18u<<8)|18u,1).d.owns);
   assert(!d(true,-7,64,48,48,8500,9000,stable,1).d.owns); // cost below 9600 ticks
   assert(!d(true,-7,64,48,48,10980,11000,stable,1).d.owns); // <5% win
   /* GMEM can win too, with symmetrical policy. */
   auto hot_gm=d(true,7,64,48,48,12000,11000,stable,1);
   assert(hot_gm.d.owns && hot_gm.workload_class==FRANE_A830_RFC5_HOT_CLOSE);
   assert(hot_gm.d.sysmem==hot_gm.d.audit);
   /* Very short passes: original RFC4 strong/stable policy remains the
    * decision, but monitoring is quieter with sparse reversible audits.
    */
   auto tiny=d(true,-7,80,48,48,350,600,stable,1);
   assert(tiny.d.owns && tiny.workload_class==FRANE_A830_RFC5_TINY_STABLE);
   assert(tiny.d.audit_log2==7 && tiny.d.measure_log2==6);
   assert(d(false,-7,80,48,48,350,600,stable,1).d.audit_log2==6);
   assert(d(true,-7,80,48,48,350,600,(3u<<16)|(20u<<8)|20u,1).workload_class
          != FRANE_A830_RFC5_TINY_STABLE);
   assert(d(true,-7,80,48,48,1200,2400,stable,1).workload_class
          != FRANE_A830_RFC5_TINY_STABLE);
   assert(d(true,-7,80,31,48,350,600,stable,1).workload_class
          != FRANE_A830_RFC5_TINY_STABLE);

   unsigned hot_audits=0,hot_measures=0,tiny_audits=0,tiny_measures=0;
   for(unsigned i=1;i<=8192;++i) {
      const auto h=d(true,-7,64,48,48,10500,11500,stable,i);
      const auto t=d(true,-7,80,48,48,350,600,stable,i);
      assert(h.d.owns && t.d.owns);
      assert(h.d.sysmem==!h.d.audit); // SYSMEM faster
      assert(t.d.sysmem==!t.d.audit);
      if(h.d.audit) {++hot_audits;assert(h.d.measure);}
      if(t.d.audit) {++tiny_audits;assert(t.d.measure);}
      hot_measures+=h.d.measure;
      tiny_measures+=t.d.measure;
   }
   assert(hot_audits==512 && tiny_audits==64);
   assert(hot_measures>=1024 && hot_measures<=1536);
   assert(tiny_measures>=128 && tiny_measures<=192);
   /* Strong RFC4 decisions must not regress in intermediate workloads. */
   auto normal=d(true,-7,64,48,48,1500,2800,stable,1);
   auto original=d(false,-7,64,48,48,1500,2800,stable,1);
   assert(normal.d.owns && normal.workload_class==FRANE_A830_RFC5_REGULAR);
   assert(normal.d.measure==original.d.measure &&
          normal.d.sysmem==original.d.sysmem &&
          normal.d.audit==original.d.audit);
   /* Timestamp magnitudes can be large, never overflow ratio comparisons. */
   assert(d(true,-7,80,48,48,UINT64_MAX/3,UINT64_MAX,stable,1).d.owns);
   puts("RFC5 hot close / tiny stable / fallback / 8192-occurrence / overflow PASS");
}
