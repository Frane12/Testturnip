#include <cassert>
#include <cstdint>
#include <iostream>

#include "frane_a830_rc1_scope_history.h"

static frane_a830_v2_tail_state
feed(frane_a830_v2_tail_state s, uint64_t sys, uint64_t gm, unsigned pairs)
{
   for (unsigned i = 0; i < pairs; i++) {
      s = frane_a830_v2_update_tail(s, true, sys);
      s = frane_a830_v2_update_tail(s, false, gm);
   }
   return s;
}

static frane_26318_smart_gmem_input
strong_layout()
{
   frane_26318_smart_gmem_input in {};
   in.layout.physical_gmem = 1024ull * 1024ull;
   in.layout.usable_gmem = 768ull * 1024ull;
   in.layout.pixels_per_tile = 230400;
   in.layout.pass_pixels = 1280ull * 720ull;
   in.layout.drawcalls = 64;
   in.sysmem_bandwidth_per_pixel = 16;
   in.gmem_bandwidth_per_pixel = 8;
   return in;
}

int main()
{
   {
      frane_a830_v2_tail_state s {};
      s = feed(s, 120, 90, 3);
      assert(!s.ready);
      assert(s.hold == 0);

      s = feed(s, 120, 90, 2);
      assert(s.ready);
      assert(s.hold == 1);
      assert(s.score >= 3);

      const auto snap =
         frane_a830_v2_unpack_tail(frane_a830_v2_pack_tail(s));
      assert(snap.ready);
      assert(snap.hold == 1);

      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, strong_layout(), {}, snap, 45, UINT64_C(1));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.learned);
      assert(!d.force_measure);
   }

   {
      frane_a830_v2_tail_state s {};
      s = feed(s, 90, 120, 5);
      assert(s.ready);
      assert(s.hold == 2);

      const auto snap =
         frane_a830_v2_unpack_tail(frane_a830_v2_pack_tail(s));
      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, strong_layout(), {}, snap, 55, UINT64_C(1));
      assert(d.override_mode);
      assert(d.select_sysmem);
      assert(d.learned);
   }

   {
      /* One contrary pair after a strongly learned GMEM regime is not allowed
       * to flip the held mode.
       */
      frane_a830_v2_tail_state s {};
      s = feed(s, 120, 90, 10);
      assert(s.hold == 1);
      const int before = s.score;

      s = feed(s, 85, 135, 1);
      assert(s.hold == 1);
      assert(s.score <= before);
   }

   {
      /* A genuine sustained regime change must still reverse the hold. */
      frane_a830_v2_tail_state s {};
      s = feed(s, 120, 90, 10);
      assert(s.hold == 1);

      s = feed(s, 85, 135, 20);
      assert(s.hold == 2);
      assert(s.score <= -3);
   }

   {
      /* Moderate history does not fight an extreme live PROFILED opinion. */
      frane_a830_v2_tail_snapshot h {};
      h.ready = true;
      h.paired_samples = 8;
      h.hold = 1;
      h.score = 4;

      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, strong_layout(), {}, h, 90, UINT64_C(1));
      assert(!d.override_mode);
   }

   {
      /* Audit slot falls through rather than injecting the loser mode. */
      frane_a830_v2_tail_snapshot h {};
      h.ready = true;
      h.paired_samples = 8;
      h.hold = 1;
      h.score = 6;

      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_LEARN, strong_layout(), {}, h, 45, UINT64_C(0));
      assert(!d.override_mode);
      assert(!d.force_measure);
   }

   {
      /* Strong measured A830 timing + structure gets a broad GMEM hold. */
      frane_2634_gmem_state measured {};
      measured.armed = true;
      measured.score = 8;

      const auto d = frane_a830_v2_decide(
         FRANE_A830_V2_BOOST, strong_layout(), measured, {}, 40, UINT64_C(1));
      assert(d.override_mode);
      assert(!d.select_sysmem);
      assert(d.measured_boost);
      assert(!d.force_measure);

      const auto audit = frane_a830_v2_decide(
         FRANE_A830_V2_BOOST, strong_layout(), measured, {}, 40, UINT64_C(0));
      assert(!audit.override_mode);
   }

   {
      /* Oversampling one mode alone never creates history confidence. */
      frane_a830_v2_tail_state s {};
      for (unsigned i = 0; i < 16; i++)
         s = frane_a830_v2_update_tail(s, true, 100);

      assert(s.paired_samples == 0);
      assert(!s.ready);
      assert(s.hold == 0);
   }

   std::cout << "A830 RC1 scope-history policy: PASS\n";
   return 0;
}
