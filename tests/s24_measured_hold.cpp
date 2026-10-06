#include "../patches/frane_s24_measured_hold.h"
#include <cassert>
#include <cstdint>
#include <iostream>

int main()
{
   {
      auto r = frane_s24_eval_measured_hold(8, 82, 41);
      assert(r.extend);
      assert(r.probe_log2 == 6);
   }
   {
      auto r = frane_s24_eval_measured_hold(8, 90, 44);
      assert(r.extend);
      assert(r.probe_log2 == 7);
   }
   {
      auto r = frane_s24_eval_measured_hold(8, 90, 45);
      assert(r.extend);
      assert(r.probe_log2 == 6);
   }

   /* Never alter the old <=40% path. */
   assert(!frane_s24_eval_measured_hold(8, 100, 40).extend);

   /* Narrow ceiling and strong dual-signal gate. */
   assert(!frane_s24_eval_measured_hold(8, 100, 47).extend);
   assert(!frane_s24_eval_measured_hold(7, 100, 44).extend);
   assert(!frane_s24_eval_measured_hold(8, 81, 44).extend);

   /* Exhaustive small-domain invariant check. */
   for (unsigned score = 0; score <= 8; score++) {
      for (unsigned structure = 0; structure <= 100; structure++) {
         for (unsigned p = 0; p <= 100; p++) {
            auto r = frane_s24_eval_measured_hold(
               uint8_t(score), uint8_t(structure), uint32_t(p));
            if (r.extend) {
               assert(score == 8);
               assert(structure >= 82);
               assert(p >= 41 && p <= 46);
               assert(r.probe_log2 == 6 || r.probe_log2 == 7);
            } else {
               assert(r.probe_log2 == 0);
            }
         }
      }
   }

   std::cout << "S2.4 MH1 policy tests passed\n";
   return 0;
}
