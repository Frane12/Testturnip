#include "frane_a810_at7_utility.h"
#include "frane_mesa_2633_a810_profile_turbo.h"
#include <cassert>
#include <cstdio>

int main() {
   frane_s1at1_context_input in{};
   in.pass_pixels=522240;in.estimated_tiles=10;in.drawcalls=45;
   in.sysmem_bandwidth_per_pixel=8;in.gmem_bandwidth_per_pixel=8;
   in.occurrences=64;in.sysmem_probability=90;
   const auto cat=frane_s1at1_catalog_for(in);
   frane_s1at3_state state{};
   state.signature=cat.signature;
   state.score=21;state.volatility=0;
   state.mode[0].samples=3;state.mode[1].samples=3;
   state.mode[0].mean=30000;state.mode[1].mean=10000;
   state.mode[0].mad=1000;state.mode[1].mad=1000;
   const uint64_t old_low40=frane_s1at3_pack(state,63)&((1ULL<<40)-1);
   auto snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(snap.signature==cat.signature && snap.samples[0]==3);
   assert(snap.at7_saving_4us>=75 && snap.at7_noise_q8<=48);
   assert((frane_s1at3_pack(state,63)&((1ULL<<40)-1))==old_low40);

   const auto a4=frane_at4_decide(in,snap,1234567);
   assert(!a4.force_measure);
   const auto a63=frane_at63_measured_winner(in,snap,1234567,a4);
   const auto a7=frane_at7_utility_winner(in,snap,1234567,a4);
   assert(!a63.override_mode && a7.override_mode && !a7.select_sysmem);
   assert(!a7.force_measure);

   auto force=a4;force.force_measure=true;
   assert(!frane_at7_utility_winner(in,snap,1234567,force).override_mode);
   auto trusted=a4;trusted.override_mode=true;
   assert(!frane_at7_utility_winner(in,snap,1234567,trusted).override_mode);

   state.mode[0].samples=4;state.mode[1].samples=4;
   snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(!frane_at7_utility_winner(in,snap,1234567,a4).override_mode);
   assert(frane_at63_measured_winner(in,snap,1234567,a4).override_mode);

   state.mode[0].samples=3;state.mode[1].samples=3;
   state.mode[0].mean=10000;state.mode[1].mean=30000;
   state.score=-21;
   snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(frane_at7_utility_winner(in,snap,1234567,a4).select_sysmem);

   state.mode[0].mean=10000;state.mode[1].mean=20000;state.score=+21;
   snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(snap.at7_saving_4us==0);
   assert(!frane_at7_utility_winner(in,snap,1234567,a4).override_mode);

   state.mode[0].mean=30000;state.mode[1].mean=28000;state.score=+21;
   snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(snap.at7_saving_4us<75);
   assert(!frane_at7_utility_winner(in,snap,1234567,a4).override_mode);

   state.mode[0].mean=30000;state.mode[1].mean=10000;
   state.mode[0].mad=20000;state.mode[1].mad=20000;
   snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(!frane_at7_utility_winner(in,snap,1234567,a4).override_mode);

   state.mode[0].mad=1000;state.mode[1].mad=1000;
   state.mode[0].age=63;
   snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(!frane_at7_utility_winner(in,snap,1234567,a4).override_mode);

   state.mode[0].age=0;state.volatility=6;
   snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(!frane_at7_utility_winner(in,snap,1234567,a4).override_mode);

   state.volatility=0;
   in.estimated_tiles=25;
   snap=frane_s1at3_unpack(frane_s1at3_pack(state,63));
   assert(!frane_at7_utility_winner(in,snap,1234567,a4).override_mode);

   std::puts("AT7 utility thresholds, 64-bit snapshot, AT63 fallback, stale/volatile/AT4-probe guards PASS");
}
