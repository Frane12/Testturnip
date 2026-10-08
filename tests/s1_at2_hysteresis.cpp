#include "../patches/frane_s1at2_hysteresis.h"
#include <cassert>
#include <cstdint>
#include <iostream>

int main()
{
   frane_s1at2_state s {};
   for (int i = 0; i < 3; i++)
      s = frane_s1at2_update_state(s, 12, 1, 0x1245, 20, 20);
   assert(s.direction == 1 && s.strength == 1);
   for (int i = 0; i < 6; i++)
      s = frane_s1at2_update_state(s, 12, 1, 0x1245, 25, 25);
   assert(s.direction == 1 && s.strength == 5);

   frane_s1at2_input in {};
   in.at1_override = true;
   in.at1_effective_sysmem_probability = 53;
   in.signature = 0x1245;
   in.learned = frane_s1at2_unpack(frane_s1at2_pack(s));
   in.decision_word = 49;
   auto d = frane_s1at2_decide(in);
   assert(d.changed && d.effective_sysmem_probability == 48);
   assert(!d.select_sysmem); /* threshold 48, word 49 */

   in.at1_force_measure = true;
   in.at1_select_sysmem = true;
   d = frane_s1at2_decide(in);
   assert(!d.changed && d.select_sysmem && d.force_measure);
   in.at1_force_measure = false;

   in.signature++;
   d = frane_s1at2_decide(in);
   assert(!d.changed && d.effective_sysmem_probability == 53);
   in.signature--;

   /* Three contradictory samples do not flip an established direction. */
   for (int i = 0; i < 3; i++)
      s = frane_s1at2_update_state(s, -12, 0, 0x1245, 25, 25);
   assert(s.direction == 1);
   for (int i = 0; i < 2; i++)
      s = frane_s1at2_update_state(s, -12, 0, 0x1245, 25, 25);
   assert(s.direction == -1 && s.strength == 1);

   s = frane_s1at2_update_state(s, -12, 12, 0x1245, 25, 25);
   assert(s.direction == 0 && s.strength == 0);
   s = frane_s1at2_update_state(s, 12, 0, 0x5280, 25, 25);
   assert(s.direction == 0 && s.signature == 0x5280);

   /* A newly discovered signature cannot inherit stale preference. */
   in.learned = frane_s1at2_unpack(frane_s1at2_pack(s));
   d = frane_s1at2_decide(in);
   assert(!d.changed);

   /* Churn and randomized flags: no invalid probability, no forced-probe loss. */
   uint64_t seed = 0x9e3779b97f4a7c15ull;
   for (unsigned k = 0; k < 150000; k++) {
      seed ^= seed << 7;
      seed ^= seed >> 9;
      seed ^= seed << 8;
      int score = int((seed >> 24) % 33) - 16;
      uint8_t volatility = uint8_t((seed >> 13) & 15);
      uint16_t sig = uint16_t((seed & 511u) + 1);
      s = frane_s1at2_update_state(s, score, volatility, sig,
                                   uint16_t((seed >> 33) & 127),
                                   uint16_t((seed >> 40) & 127));
      in.signature = sig;
      in.learned = frane_s1at2_unpack(frane_s1at2_pack(s));
      in.at1_effective_sysmem_probability = uint32_t(seed % 101u);
      in.at1_force_measure = bool(seed & (1ull << 20));
      in.at1_select_sysmem = bool(seed & (1ull << 21));
      in.at1_override = bool(seed & (1ull << 22));
      in.decision_word = seed;
      d = frane_s1at2_decide(in);
      assert(d.effective_sysmem_probability <= 100);
      assert(!d.changed || (d.effective_sysmem_probability >= 4 &&
                            d.effective_sysmem_probability <= 96));
      if (in.at1_force_measure) {
         assert(!d.changed && d.force_measure &&
                d.select_sysmem == in.at1_select_sysmem);
      }
   }
   std::cout << "AT2 policy tests passed\n";
}
