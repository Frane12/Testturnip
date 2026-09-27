/* SPDX-License-Identifier: MIT
 * Frane Mesa 26.3.5 A810 SHADER-PIPELINE EXP.
 * Pure policy helpers. Experimental downstream code, not official Mesa.
 */
#ifndef FRANE_MESA_2635_SHADER_PIPELINE_H
#define FRANE_MESA_2635_SHADER_PIPELINE_H

#include <cstdint>

#define FRANE_2635_STAGE_NIR_KEY_SUFFIX 0x4eu /* 'N' */
#define FRANE_2635_STAGE_NIR_MAX_ENTRIES 384u

static inline bool
frane_2635_is_a810_chip(uint64_t chip_id)
{
   return chip_id == UINT64_C(0x44010000) ||
          chip_id == UINT64_C(0xffff44010000);
}

struct frane_2635_stage_probe_state {
   bool all_hit = true;
   bool application_hit = true;
   uint64_t hit_mask = 0;
};

static inline void
frane_2635_record_stage_probe(frane_2635_stage_probe_state &state,
                              unsigned stage,
                              bool shader_found,
                              bool application_cache_hit)
{
   if (!shader_found) {
      state.all_hit = false;
      state.application_hit = false;
      return;
   }

   if (stage < 64)
      state.hit_mask |= UINT64_C(1) << stage;

   state.application_hit &= application_cache_hit;
}

static inline bool
frane_2635_stage_was_cached(uint64_t hit_mask, unsigned stage)
{
   return stage < 64 && (hit_mask & (UINT64_C(1) << stage));
}

#endif
