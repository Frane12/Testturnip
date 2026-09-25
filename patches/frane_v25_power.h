/* SPDX-License-Identifier: MIT
 * A810-only experimental KGSL power-constraint gating.
 * Never write undocumented GPU MMIO registers or disable thermal policy.
 */
#pragma once
#include <stdint.h>
#include <stdbool.h>

static inline bool
frane_v25_is_a810(uint64_t chip_id)
{
   return chip_id == UINT64_C(0x44010000) ||
          chip_id == UINT64_C(0xffff44010000);
}

static inline bool
frane_v25_refresh_due(uint32_t successful_submissions)
{
   /* Period 256: inexpensive bit mask, and never refresh at counter=0. */
   return successful_submissions != 0 &&
          (successful_submissions & 255u) == 0u;
}
