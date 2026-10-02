#include <cassert>
#include <cstdint>
#include <iostream>

static unsigned sched_window(unsigned pressure, unsigned max_window = 4)
{
   if (pressure < 12)
      return max_window;
   if (pressure < 30)
      return max_window < 3 ? max_window : 3;
   return max_window < 2 ? max_window : 2;
}

struct GmemDecision {
   bool eligible;
   unsigned probe_log2;
};

static GmemDecision armed_gmem(unsigned prob, unsigned score, unsigned structure)
{
   if (prob > 65)
      return {false, 0};
   if (score >= 8 && structure >= 72 && prob <= 35)
      return {true, 10};
   if (score >= 6 && structure >= 62 && prob <= 50)
      return {true, 9};
   if (score >= 4 && structure >= 54)
      return {true, 8};
   return {false, 0};
}

static unsigned cold_effective(unsigned prob, unsigned structure)
{
   if (prob > 75 || structure < 56)
      return 1000;

   unsigned reduction = 32;
   if (structure >= 88)
      reduction = 52;
   else if (structure >= 76)
      reduction = 42;

   unsigned e = prob > reduction ? prob - reduction : 0;
   return e < 1 ? 1 : e;
}

int main()
{
   assert(sched_window(0) == 4);
   assert(sched_window(11) == 4);
   assert(sched_window(12) == 3);
   assert(sched_window(29) == 3);
   assert(sched_window(30) == 2);
   assert(sched_window(100) == 2);

   auto a = armed_gmem(30, 8, 75);
   assert(a.eligible && a.probe_log2 == 10);
   auto b = armed_gmem(45, 6, 64);
   assert(b.eligible && b.probe_log2 == 9);
   auto c = armed_gmem(60, 4, 56);
   assert(c.eligible && c.probe_log2 == 8);
   assert(!armed_gmem(66, 9, 99).eligible);

   assert(cold_effective(60, 90) == 8);
   assert(cold_effective(40, 80) == 1);
   assert(cold_effective(76, 90) == 1000);
   assert(cold_effective(30, 55) == 1000);

   std::cout << "A810 MAX-PERF LAB V1.0 policy model: PASS\n";
   return 0;
}
