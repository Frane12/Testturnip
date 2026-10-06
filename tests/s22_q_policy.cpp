#include "../patches/frane_s22_q_policy.h"
#include <cassert>
#include <cstdint>
#include <iostream>

static frane_s22_q_rp_input base()
{
   frane_s22_q_rp_input in {};
   in.draw_count = 64;
   in.sysmem_bandwidth_per_pixel = 24;
   in.gmem_bandwidth_per_pixel = 12;
   return in;
}

int main()
{
   {
      frane_s22_q_rp_input in {};
      auto out = frane_s22_q_eval(in);
      assert(!out.valid);
      assert(out.score_delta == 0);
   }
   {
      /* Positive bias requires bandwidth + density + LRZ quality together. */
      auto in = base();
      in.lrz_candidate_draw_count = 40;
      in.lrz_late_draw_count = 4;
      auto out = frane_s22_q_eval(in);
      assert(out.score_delta > 0);
      assert(out.score_delta <= 4);

      auto no_lrz = in;
      no_lrz.lrz_candidate_draw_count = 0;
      no_lrz.lrz_late_draw_count = 0;
      assert(frane_s22_q_eval(no_lrz).score_delta <= 0);

      auto sparse = in;
      sparse.draw_count = 20;
      assert(frane_s22_q_eval(sparse).score_delta <= 0);

      auto poor_bw = in;
      poor_bw.gmem_bandwidth_per_pixel = 24;
      assert(frane_s22_q_eval(poor_bw).score_delta <= 0);
   }
   {
      auto in = base();
      in.draw_count = 128;
      in.indirect_draw_count = 48;
      in.lrz_candidate_draw_count = 100;
      in.lrz_late_draw_count = 10;
      auto out = frane_s22_q_eval(in);
      assert(out.score_delta >= 3);
      assert(out.score_delta <= 4);
   }
   {
      auto good = base();
      good.lrz_candidate_draw_count = 40;
      good.lrz_late_draw_count = 4;
      auto bad = good;
      bad.lrz_late_draw_count = 30;
      bad.lrz_disabled_at_draw_plus1 = 2;
      bad.lrz_write_disabled_at_draw_plus1 = 3;
      assert(frane_s22_q_eval(bad).score_delta <
             frane_s22_q_eval(good).score_delta);
   }
   {
      auto in = base();
      in.draw_count = 4;
      in.gmem_bandwidth_per_pixel = 28;
      auto out = frane_s22_q_eval(in);
      assert(out.valid);
      assert(out.score_delta < 0);
      assert(out.score_delta >= -4);
   }
   {
      auto in = base();
      in.lrz_candidate_draw_count = 40;
      in.lrz_late_draw_count = 4;
      in.stencil_draw_count = 8;
      in.stencil_last_draw = 63;
      const auto late = frane_s22_q_eval(in).score_delta;
      in.stencil_last_draw = 10;
      const auto early = frane_s22_q_eval(in).score_delta;
      assert(late <= early);
   }
   {
      uint64_t x = 0x9e3779b97f4a7c15ULL;
      for (unsigned i = 0; i < 200000; i++) {
         x ^= x << 7; x ^= x >> 9; x ^= x << 8;
         frane_s22_q_rp_input in {};
         in.draw_count = 1 + uint32_t(x & 1023);
         in.indirect_draw_count = uint32_t((x >> 10) & 255);
         in.lrz_candidate_draw_count = uint32_t((x >> 18) & 1023);
         in.lrz_late_draw_count = uint32_t((x >> 28) & 1023);
         in.stencil_draw_count = uint32_t((x >> 38) & 127);
         in.stencil_last_draw = uint32_t((x >> 45) & 1023);
         in.sysmem_bandwidth_per_pixel = 1 + uint32_t((x >> 5) & 255);
         in.gmem_bandwidth_per_pixel = 1 + uint32_t((x >> 13) & 255);
         if (x & (1ULL << 60))
            in.lrz_disabled_at_draw_plus1 = 1 + uint32_t((x >> 20) & 1023);
         if (x & (1ULL << 61))
            in.lrz_write_disabled_at_draw_plus1 = 1 + uint32_t((x >> 30) & 1023);
         auto out = frane_s22_q_eval(in);
         assert(out.valid);
         assert(out.score_delta >= -4 && out.score_delta <= 4);
      }
   }

   std::cout << "S2.3 Q2 policy tests passed\n";
   return 0;
}
