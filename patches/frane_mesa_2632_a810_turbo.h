/* SPDX-License-Identifier: MIT
 * Frane Mesa 26.3.2 A810 TURBO EXP: pure policy helpers.
 * Experimental downstream patchset; not an official Mesa release.
 */
#ifndef FRANE_MESA_2632_A810_TURBO_H
#define FRANE_MESA_2632_A810_TURBO_H

#include <algorithm>
#include <cstdint>

static inline uint32_t
frane_2632_profile_base_interval(uint32_t normal_base, bool is_a810)
{
   return is_a810 ? std::max(normal_base, 16u) : normal_base;
}

static inline bool
frane_2632_maintenance_due(uint32_t ticket)
{
   /* 1/128 submit cadence. Ticket zero intentionally runs maintenance. */
   return (ticket & 127u) == 0u;
}

static inline bool
frane_2632_power_refresh_due(uint32_t successful_submissions)
{
   /* PWR_MAX was accepted at queue creation. Refresh only once per 1024
    * successful submits to keep SETPROPERTY out of the ordinary frame path.
    */
   return successful_submissions != 0 &&
          (successful_submissions & 1023u) == 0u;
}

#endif
