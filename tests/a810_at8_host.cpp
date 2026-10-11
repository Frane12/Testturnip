// SPDX-License-Identifier: MIT
// AT8 A810 host behavior: do not rely on an actual GPU for source assertions.
#include "frane_a810_at8_early.h"
#include "frane_mesa_2633_a810_profile_turbo.h"
#include <cassert>
#include <cstdio>

int main() {
   frane_s1at1_context_input in{};
   in.pass_pixels=522240; in.estimated_tiles=10; in.drawcalls=45;
   in.sysmem_bandwidth_per_pixel=8; in.gmem_bandwidth_per_pixel=8;
   in.occurrences=64; in.sysmem_probability=75;
   const auto cat=frane_s1at1_catalog_for(in);
   frane_s1at3_state st{};
   st.signature=cat.signature;
   st.score=23; st.volatility=0;
   st.mode[0].samples=2; st.mode[1].samples=2;
   st.mode[0].mean=60000; st.mode[1].mean=10000;
   st.mode[0].mad=1000; st.mode[1].mad=1000;
   const uint64_t packed=frane_s1at3_pack(st,64);
   const auto s=frane_s1at3_unpack(packed);
   assert(s.samples[0]==2 && s.samples[1]==2);
   assert(s.at7_saving_4us >= 150 && s.at7_noise_q8 <= 24);
   frane_s1at1_decision at4{};
   auto a8=frane_at8_early_winner(in,s,424242,at4);
   assert(a8.override_mode && !a8.select_sysmem);
   assert(!frane_at7_utility_winner(in,s,424242,at4).override_mode);
   assert(!frane_at63_measured_winner(in,s,424242,at4).override_mode);
   at4.force_measure=true;
   assert(!frane_at8_early_winner(in,s,424242,at4).override_mode);
   at4.force_measure=false; at4.override_mode=true;
   assert(!frane_at8_early_winner(in,s,424242,at4).override_mode);
   at4.override_mode=false;

   st.mode[0].samples=3; st.mode[1].samples=3;
   assert(!frane_at8_early_winner(in,frane_s1at3_unpack(frane_s1at3_pack(st,64)),424242,at4).override_mode);
   st.mode[0].samples=2; st.mode[1].samples=2;
   st.score=-23; st.mode[0].mean=10000; st.mode[1].mean=60000;
   a8=frane_at8_early_winner(in,frane_s1at3_unpack(frane_s1at3_pack(st,64)),424242,at4);
   assert(a8.override_mode && a8.select_sysmem);
   st.score=+23;
   assert(!frane_at8_early_winner(in,frane_s1at3_unpack(frane_s1at3_pack(st,64)),424242,at4).override_mode);
   st.mode[0].mean=60000; st.mode[1].mean=10000; st.score=+10;
   assert(!frane_at8_early_winner(in,frane_s1at3_unpack(frane_s1at3_pack(st,64)),424242,at4).override_mode);
   st.score=+23; st.mode[0].mad=40000; st.mode[1].mad=40000;
   assert(!frane_at8_early_winner(in,frane_s1at3_unpack(frane_s1at3_pack(st,64)),424242,at4).override_mode);
   st.mode[0].mad=1000; st.mode[1].mad=1000;
   auto stale=frane_s1at3_unpack(frane_s1at3_pack(st,64));
   stale.stale[0]=true; // deterministic stale snapshot test, independent of timestamp wrap
   assert(!frane_at8_early_winner(in,stale,424242,at4).override_mode);
   st.mode[0].age=0; st.volatility=1;
   assert(!frane_at8_early_winner(in,frane_s1at3_unpack(frane_s1at3_pack(st,64)),424242,at4).override_mode);
   st.volatility=0; in.estimated_tiles=25;
   assert(!frane_at8_early_winner(in,frane_s1at3_unpack(frane_s1at3_pack(st,64)),424242,at4).override_mode);
   std::puts("A810 AT8: 2 paired, conservative saved GPU time, fallback, stale/noisy, AT4 guards PASS");
}
