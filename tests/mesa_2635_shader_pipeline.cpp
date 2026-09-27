// SPDX-License-Identifier: MIT
#include "../patches/frane_mesa_2635_shader_pipeline.h"

#include <cassert>
#include <cstdio>

int main()
{
   assert(frane_2635_is_a810_chip(UINT64_C(0x44010000)));
   assert(frane_2635_is_a810_chip(UINT64_C(0xffff44010000)));
   assert(!frane_2635_is_a810_chip(UINT64_C(0x44020000)));

   frane_2635_stage_probe_state p{};
   frane_2635_record_stage_probe(p, 0, false, false);
   /* Critical regression test: a first-stage miss must NOT prevent a later
    * stage hit from being recorded. */
   frane_2635_record_stage_probe(p, 4, true, true);
   assert(!p.all_hit);
   assert(!p.application_hit);
   assert(!frane_2635_stage_was_cached(p.hit_mask, 0));
   assert(frane_2635_stage_was_cached(p.hit_mask, 4));

   frane_2635_stage_probe_state full{};
   frane_2635_record_stage_probe(full, 0, true, true);
   frane_2635_record_stage_probe(full, 4, true, true);
   assert(full.all_hit && full.application_hit);
   assert(frane_2635_stage_was_cached(full.hit_mask, 0));
   assert(frane_2635_stage_was_cached(full.hit_mask, 4));

   frane_2635_stage_probe_state app_miss{};
   frane_2635_record_stage_probe(app_miss, 0, true, false);
   frane_2635_record_stage_probe(app_miss, 4, true, true);
   assert(app_miss.all_hit);
   assert(!app_miss.application_hit);

   assert(FRANE_2635_STAGE_NIR_KEY_SUFFIX == unsigned('N'));
   assert(FRANE_2635_STAGE_NIR_MAX_ENTRIES == 384u);

   std::puts("PASS: Mesa 26.3.5 shader/pipeline policy");
}
