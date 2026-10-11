// SPDX-License-Identifier: MIT
// AT9 A810 FC2 host-only policy tests. Validate strong/weak/noisy/stale controls.
#include "frane_a810_at9_fc2.h"
#include "frane_mesa_2633_a810_profile_turbo.h"
#include <cassert>
#include <cstdio>
int main() {
   frane_s1at1_context_input in{};
   in.pass_pixels=522240;in.estimated_tiles=10;in.drawcalls=209;
   in.sysmem_bandwidth_per_pixel=0;in.gmem_bandwidth_per_pixel=16;
   in.occurrences=1024;in.sysmem_probability=50;
   const auto cat=frane_s1at1_catalog_for(in);
   frane_s1at3_snapshot s{};
   s.signature=cat.signature;
   frane_s1at1_decision at4{};
   // High-draw prior is uncertain by design, never locks the mode.
   const auto p_sys=frane_at9_fc2_prior(in,s,10,at4);
   const auto p_gm=frane_at9_fc2_prior(in,s,90,at4);
   assert(p_sys.override_mode && p_sys.select_sysmem && p_sys.effective_sysmem_probability==64);
   assert(p_gm.override_mode && !p_gm.select_sysmem);
   at4.force_measure=true;
   assert(!frane_at9_fc2_prior(in,s,10,at4).override_mode);
   assert(!frane_at9_fc2_measured(in,s,10,at4,false).override_mode);
   at4.force_measure=false;
   s.samples[0]=3;s.samples[1]=3;s.score=-15;s.volatility=3;
   s.at7_saving_4us=250;s.at7_noise_q8=44;
   auto win=frane_at9_fc2_measured(in,s,90,at4,false);
   assert(win.override_mode && win.select_sysmem && win.confidence==15);
   assert(!frane_at9_fc2_prior(in,s,20,at4).override_mode);
   // Legacy AT4 can be overruled only if not actively measuring.
   at4.override_mode=true;at4.select_sysmem=false;
   win=frane_at9_fc2_measured(in,s,90,at4,false);
   assert(win.override_mode && win.select_sysmem);
   assert(!frane_at9_fc2_measured(in,s,90,at4,true).override_mode);
   at4.override_mode=false;
   s.at7_saving_4us=74;
   assert(!frane_at9_fc2_measured(in,s,90,at4,false).override_mode);
   s.samples[0]=4;s.samples[1]=5;s.score=7;s.at7_saving_4us=60;s.at7_noise_q8=90;s.volatility=5;
   win=frane_at9_fc2_measured(in,s,90,at4,false);
   assert(win.override_mode && win.select_sysmem);
   s.at7_noise_q8=97;
   assert(!frane_at9_fc2_measured(in,s,90,at4,false).override_mode);
   s.at7_noise_q8=90;s.stale[0]=true;
   assert(!frane_at9_fc2_measured(in,s,90,at4,false).override_mode);
   s.stale[0]=false;s.volatility=6;
   assert(!frane_at9_fc2_measured(in,s,90,at4,false).override_mode);
   s.volatility=1;
   in.sysmem_bandwidth_per_pixel=4;
   assert(!frane_at9_fc2_measured(in,s,90,at4,false).override_mode);
   assert(!frane_at9_fc2_prior(in,s,90,at4).override_mode);
   in.sysmem_bandwidth_per_pixel=0;
   in.drawcalls=20;
   assert(!frane_at9_fc2_measured(in,s,90,at4,false).override_mode);
   puts("AT9 FC2 measured winner, 64pct uncertain prior, A810 scope, probe, stale, volatile, rollback PASS");
}
