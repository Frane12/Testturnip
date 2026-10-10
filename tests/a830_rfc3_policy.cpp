#include "frane_a830_rfc3.h"
#include <cassert>
#include <cstdint>
#include <cstdio>

int main() {
   const uint64_t hash=0x12345678abcdull;
   auto select=[&](bool enabled, bool ready, int score, unsigned pairs,
                   unsigned sysn,unsigned gmn, uint64_t sys, uint64_t gm,
                   unsigned occurrence) {
      return frane_a830_rfc3_select(enabled,ready,score,pairs,sysn,gmn,sys,gm,
                                   occurrence,hash);
   };
   assert(!select(false,true,-7,64,64,64,80,100,1).owns);
   assert(!select(true,false,-7,64,64,64,80,100,1).owns);
   assert(!select(true,true,-5,64,64,64,80,100,1).owns);
   assert(!select(true,true,-7,15,64,64,80,100,1).owns);
   assert(!select(true,true,-7,64,7,64,80,100,1).owns);
   assert(!select(true,true,-7,64,64,7,80,100,1).owns);
   assert(!select(true,true,-7,64,64,64,0,100,1).owns);
   assert(!select(true,true,-7,64,64,64,80,0,1).owns);
   assert(!select(true,true,-7,64,64,64,91,100,1).owns);
   assert(select(true,true,-6,16,8,8,90,100,1).owns);
   /* A/B opt out always falls back to original mode; no stale state. */
   unsigned audits=0,sys=0,measured=0;
   for(unsigned i=1;i<=4096;i++) {
      auto a=select(true,true,-7,100,100,100,60,100,i);
      assert(a.owns);
      if(a.audit) {
         ++audits;
         assert(!a.sysmem && a.measure);
      } else {
         ++sys;
         assert(a.sysmem);
      }
      measured+=a.measure;
   }
   assert(audits==64 && sys==4032);
   assert(measured>=512 && measured<=580);
   /* If measured regime improves, fallback without permanently locking it. */
   assert(!select(true,true,-7,100,100,100,95,100,4097).owns);
   assert(!select(true,true,0,100,100,100,60,100,4097).owns);
   assert(!select(true,true,-7,100,100,100,60,100,0).owns);
   /* Large GPU timestamp counters cannot overflow ratios. */
   assert(select(true,true,-7,100,100,100,
            UINT64_MAX/3,UINT64_MAX,9).owns);
   puts("A830 RFC3 guard threshold / audit / recovery / overflow host PASS");
}
