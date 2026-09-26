// SPDX-License-Identifier: MIT
#include "../patches/frane_mesa_2631_sync.h"

#include <cassert>
#include <climits>
#include <cstdint>
#include <cstdio>

static bool ts_after_eq(uint32_t a, uint32_t b)
{
   return (int32_t)(a - b) >= 0;
}

static uint32_t min_ts(uint32_t a, uint32_t b)
{
   return ts_after_eq(a, b) ? b : a;
}

int main()
{
   assert(frane_2631_deadline_ns(100, 50) == 150);
   assert(frane_2631_deadline_ns(100, UINT64_MAX) == UINT64_MAX);
   assert(frane_2631_deadline_ns(UINT64_MAX - 3, 10) == UINT64_MAX);

   assert(frane_2631_relative_ms(5'000'000ull, 4'000'000ull) == 0);
   assert(frane_2631_relative_ms(5'000'000ull, 9'000'000ull) == 4);
   assert(frane_2631_relative_ms(0, UINT64_MAX) == -1);
   assert(frane_2631_relative_ms(0, uint64_t(INT_MAX + 1000ull) * 1000000ull) == INT_MAX);

   assert(frane_2631_poll_outcome_from_ret(2) == FRANE_2631_POLL_READY);
   assert(frane_2631_poll_outcome_from_ret(0) == FRANE_2631_POLL_TIMEOUT);
   assert(frane_2631_poll_outcome_from_ret(-1) == FRANE_2631_POLL_ERROR);

   assert(min_ts(10, 20) == 10);
   assert(min_ts(20, 10) == 10);
   /* 32-bit timestamp wrap: 0x10 is later than 0xfffffff0, so earliest is old value. */
   assert(min_ts(0x10u, 0xfffffff0u) == 0xfffffff0u);

   std::puts("PASS: Mesa 26.3.1 EXP timeout/poll/timestamp helpers");
}
