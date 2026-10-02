#include <cassert>
#include <cstdint>
#include <iostream>

#include "frane_a810_rc1_pass_history.h"

static frane_rc1_history_state
feed(frane_rc1_history_state s, uint64_t sys, uint64_t gm, unsigned pairs)
{
   for (unsigned i = 0; i < pairs; i++) {
      s = frane_rc1_update_history(s, true, sys);
      s = frane_rc1_update_history(s, false, gm);
   }
   return s;
}

int main()
{
   {
      frane_rc1_history_state s {};
      s = feed(s, 120, 90, 3);
      assert(s.paired_samples == 3);
      assert(s.hold == 0);

      s = feed(s, 120, 90, 2);
      assert(s.hold == 1);
      assert(s.score >= 3);

      const auto snap =
         frane_rc1_unpack_history(frane_rc1_pack_history(s));
      assert(snap.hold == 1);

      auto d = frane_rc1_decide_history(
         true, true, snap, 40, UINT64_C(1));
      assert(d.override_mode && !d.select_sysmem);

      d = frane_rc1_decide_history(
         true, true, snap, 40, UINT64_C(0));
      assert(!d.override_mode && d.audit);
   }

   {
      frane_rc1_history_state s {};
      s = feed(s, 90, 120, 5);
      assert(s.hold == 2);

      const auto snap =
         frane_rc1_unpack_history(frane_rc1_pack_history(s));
      const auto d = frane_rc1_decide_history(
         true, true, snap, 60, UINT64_C(1));
      assert(d.override_mode && d.select_sysmem);
   }

   {
      frane_rc1_history_state s {};
      s = feed(s, 120, 90, 5);
      assert(s.hold == 1);
      assert(s.score >= 3 && s.score < 6);

      const auto snap =
         frane_rc1_unpack_history(frane_rc1_pack_history(s));
      const auto d = frane_rc1_decide_history(
         true, true, snap, 90, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      frane_rc1_history_state s {};
      s = feed(s, 120, 90, 10);
      assert(s.hold == 1);

      s = feed(s, 85, 135, 18);
      assert(s.hold == 2);
      assert(s.score <= -3);
   }

   {
      frane_rc1_history_state s {};
      for (unsigned i = 0; i < 12; i++)
         s = frane_rc1_update_history(s, true, 100);

      assert(s.paired_samples == 0);
      assert(s.hold == 0);

      s = frane_rc1_update_history(s, false, 90);
      assert(s.paired_samples == 1);
      assert(s.hold == 0);
   }

   {
      frane_rc1_history_state s {};
      s = frane_rc1_update_history(s, true, 0);
      s = frane_rc1_update_history(s, false, 0);
      assert(s.sysmem.samples == 0 && s.gmem.samples == 0);
   }

   {
      frane_rc1_history_snapshot snap {};
      snap.hold = 1;
      snap.paired_samples = 10;
      snap.score = 5;

      assert(!frane_rc1_decide_history(
         true, false, snap, 50, UINT64_C(1)).override_mode);
      assert(!frane_rc1_decide_history(
         false, true, snap, 50, UINT64_C(1)).override_mode);
   }

   std::cout << "A810 RC1 pass-history hysteresis model: PASS\n";
   return 0;
}
