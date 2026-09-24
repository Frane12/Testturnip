#include "../patches/frane_profiled_policy.h"
#include <cassert>
#include <cstdio>
#include <limits>

int main()
{
   assert(frane_profiled_winner(0, 100) == 0);
   assert(frane_profiled_winner(100, 0) == 0);
   assert(frane_profiled_winner(100, 100) == 0);
   assert(frane_profiled_winner(100, 139) == 0);
   assert(frane_profiled_winner(100, 140) == 1);
   assert(frane_profiled_winner(10000, 10300) == 0);
   assert(frane_profiled_winner(10000, 10301) == 1);
   assert(frane_profiled_winner(10301, 10000) == -1);
   const uint64_t max = std::numeric_limits<uint64_t>::max();
   assert(frane_profiled_winner(max, max - 1) == 0);
   assert(frane_profiled_winner(1, max) == 1);
   assert(frane_profiled_winner(max, 1) == -1);
   // Exhaustive symmetry and monotonicity across short render-pass timings.
   for (uint64_t a = 1; a <= 3000; a++) {
      int previous = 0;
      for (uint64_t b = a; b <= a + 400; b++) {
         int winner = frane_profiled_winner(a, b);
         assert(winner == -frane_profiled_winner(b, a));
         assert(winner >= previous);
         previous = winner;
      }
   }
   puts("PASS: invalid inputs, absolute/relative threshold, symmetry, monotonicity, uint64 extremes");
}
