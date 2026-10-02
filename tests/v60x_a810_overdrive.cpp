#include <cassert>
#include <cstdint>
#include <iostream>

struct State {
   bool armed;
   unsigned score;
};

static unsigned sy_window_default(unsigned requested)
{
   if (requested < 2) return 2;
   if (requested > 8) return 8;
   return requested;
}

static bool armed_overdrive_eligible(State s, unsigned structure,
                                     unsigned sysmem_probability)
{
   if (!s.armed || sysmem_probability > 70)
      return false;

   if (s.score >= 8 && structure >= 70 && sysmem_probability <= 40)
      return true;
   if (s.score >= 6 && structure >= 60 && sysmem_probability <= 52)
      return true;
   if (s.score >= 4 && structure >= 52)
      return true;
   return false;
}

static bool cold_overdrive_eligible(unsigned structure,
                                    unsigned sysmem_probability)
{
   return sysmem_probability <= 75 && structure >= 56;
}

int main()
{
   // Scheduler default and clamp.
   assert(sy_window_default(2) == 2);
   assert(sy_window_default(0) == 2);
   assert(sy_window_default(4) == 4);
   assert(sy_window_default(99) == 8);

   // Measured frontier: deliberately wider than V56 but still bounded.
   assert(armed_overdrive_eligible({true, 8}, 70, 40));
   assert(armed_overdrive_eligible({true, 6}, 60, 52));
   assert(armed_overdrive_eligible({true, 4}, 52, 70));
   assert(!armed_overdrive_eligible({true, 4}, 52, 71));
   assert(!armed_overdrive_eligible({true, 3}, 90, 10));
   assert(!armed_overdrive_eligible({false, 9}, 99, 0));

   // Cold path boundary.
   assert(cold_overdrive_eligible(56, 75));
   assert(!cold_overdrive_eligible(55, 20));
   assert(!cold_overdrive_eligible(90, 76));

   std::cout << "A810 V60X OVERDRIVE policy model: PASS\n";
   return 0;
}
