#include <cassert>
#include <cstdint>
#include <iostream>
#include "frane_a830_s2_bw3.h"

int main()
{
   frane_a830_s2bw2_eval base{};
   auto invalid=frane_a830_s2bw3_adjust(base,64,24,8,7,16,true);
   assert(!invalid.valid);
   base.valid=true;
   base.estimated_tiles=4;
   base.score_delta=32;
   auto cold=frane_a830_s2bw3_adjust(base,96,24,8,7,0,false);
   assert(cold.valid && cold.score_delta==0);
   auto confirmed=frane_a830_s2bw3_adjust(base,96,24,8,7,16,true);
   assert(confirmed.valid && confirmed.score_delta==4);
   auto history_negative=frane_a830_s2bw3_adjust(base,96,24,8,-7,16,true);
   assert(history_negative.valid && history_negative.score_delta==0);
   base.rollback_sysmem=true;
   assert(frane_a830_s2bw3_adjust(base,96,24,8,7,16,true).score_delta==0);
   base.rollback_sysmem=false;
   base.estimated_tiles=8;
   assert(frane_a830_s2bw3_adjust(base,40,24,8,7,16,true).score_delta==2);
   base.estimated_tiles=20;
   assert(frane_a830_s2bw3_adjust(base,15,8,16,-7,16,true).score_delta==-3);
   base.hold_gmem=true;
   assert(frane_a830_s2bw3_adjust(base,15,8,16,-7,16,true).score_delta==0);
   base.hold_gmem=false;

   unsigned tests=0;
   for(uint64_t tiles=1;tiles<=64;tiles++)
      for(uint32_t draws: {1u,8u,16u,64u,256u})
         for(int hist: {-8,-3,0,3,8})
            for(uint32_t gm: {2u,8u,16u,32u}) {
               base.estimated_tiles=tiles;
               auto a=frane_a830_s2bw3_adjust(base,draws,24u,gm,
                                                int8_t(hist),16,true);
               auto b=frane_a830_s2bw3_adjust(base,draws,24u,gm,
                                                int8_t(hist),16,true);
               assert(a.valid && a.score_delta==b.score_delta);
               assert(a.score_delta>=-3 && a.score_delta<=4);
               if(hist==0)assert(a.score_delta==0);
               tests++;
            }
   std::cout << "A830 BW3 Tile Cost Lite policy PASS: " << tests << " cases\n";
}
