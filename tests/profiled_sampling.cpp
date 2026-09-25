#include "../patches/frane_profiled_sampling.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>
#include <limits>

int main()
{
   for (int invalid : {-9, 0, 3, 5, 17, 100})
      assert(frane_profiled_sample_interval(invalid) == 4);
   for (uint32_t n : {1u, 2u, 4u, 8u, 16u}) {
      assert(frane_profiled_sample_interval(n) == n);
      for (uint32_t p = 0; p <= 100; p++) {
         for (bool sysmem : {false, true}) {
            const uint32_t period = frane_profiled_sample_period(p, sysmem, n);
            if (p == 0 || p == 100) {
               assert(period == 0);
            } else if ((p >= 95 && sysmem) || (p <= 5 && !sysmem)) {
               assert(period == n);
            } else {
               assert(period == 1); // Every uncertain/losing mode is measured.
            }
         }
      }
      // Any phase, including ticket wrap, yields exactly 1/N measurements.
      for (uint32_t start : {0u, 1u, 13u, std::numeric_limits<uint32_t>::max() - 7}) {
         unsigned sampled = 0;
         uint32_t ticket = start;
         for (unsigned i = 0; i < 1024; i++, ticket++)
            sampled += (ticket & (n - 1)) == 0;
         assert(sampled == 1024 / n);
      }
   }
   // V18 warm-up uses 20/80, which must always remain fully measured.
   for (bool sysmem : {false, true}) {
      assert(frane_profiled_sample_period(20, sysmem, 4) == 1);
      assert(frane_profiled_sample_period(80, sysmem, 4) == 1);
   }
   puts("PASS: full warm-up, losing probes, all probabilities, intervals, phase and counter wrap");
}
