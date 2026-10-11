/* SPDX-License-Identifier: MIT
 * Optional cold-history V3 shortcut. The GPU winner predicate cannot be
 * satisfied if the category is mismatched, stale or lacks two paired samples.
 * This eliminates pointless category cache/phase CAS during cold learning;
 * on valid evidence, the original V3 executes unchanged. A/B opt-in.
 */
#ifndef FRANE_A810_V3_COLD_FASTPATH_H
#define FRANE_A810_V3_COLD_FASTPATH_H
#include "frane_a810_atultimate_v3.h"
static inline bool frane_v3_no_possible_candidate(
   const frane_s1at1_context_input &in,
   const frane_s1at3_snapshot &snap)
{
   const auto cat=frane_s1at1_catalog_for(in);
   return !cat.signature || snap.signature != cat.signature ||
      snap.stale[0] || snap.stale[1] ||
      std::min(snap.samples[0],snap.samples[1]) < 2;
}
#endif
