#include "frane_switch_policy.h"
#include "frane_mesa_2634_a810_gmem_runtime.h"
#include "frane_mesa_26364_a810_smart_v2.h"
#include <cassert>
#include <cstdio>
#include <limits>

int main()
{
   frane_switch_small_input in {true, true, true, true, 2, 262144, 1, 8, 8};
   assert(frane_switch_tune_small(in));
   unsigned cases = 0;
   for (unsigned flags=0; flags<16; ++flags)
   for (uint32_t draws=0; draws<=10; ++draws)
   for (uint64_t pixels : {UINT64_C(0),UINT64_C(262143),UINT64_C(262144),UINT64_MAX})
   for (uint64_t tiles : {UINT64_C(0),UINT64_C(1),UINT64_C(16),UINT64_C(17),UINT64_MAX})
   for (uint64_t resident : {UINT64_C(0),UINT64_C(8),UINT64_MAX})
   for (uint64_t transfer : {UINT64_C(0),UINT64_C(8),UINT64_C(9),UINT64_MAX}) {
      in = {bool(flags&1),bool(flags&2),bool(flags&4),bool(flags&8),draws,pixels,tiles,resident,transfer};
      bool accept=frane_switch_tune_small(in);
      if (accept) {
         assert(flags==15 && draws>=2 && draws<=4);
         assert(pixels>=262144 && tiles && tiles<=16);
         assert(resident && transfer<=resident);
      }
      if (flags==15 && draws==2 && pixels==262144 && tiles==1 && resident==8 && transfer==8)
         assert(accept);
      ++cases;
   }
   frane_2634_gmem_layout_input layout {};
   layout.physical_gmem=576*1024;
   layout.usable_gmem=512*1024;
   layout.pixels_per_tile=65536;
   layout.pass_pixels=1280*720;
   layout.selected_tile_count=16;
   for (uint32_t d=0; d<=5; ++d) {
      layout.drawcalls=d;
      layout.short_pass_eligible=false;
      assert(frane_2634_eval_layout(layout).eligible==(d>=5));
      layout.short_pass_eligible=true;
      assert(frane_2634_eval_layout(layout).eligible==(d>=2));
   }
   layout.drawcalls=2;
   layout.short_pass_eligible=true;
   layout.pass_pixels=UINT64_MAX;
   assert(!frane_2634_eval_layout(layout).eligible);
   layout.pass_pixels=1280*720;
   layout.selected_tile_count=25;
   assert(!frane_2634_eval_layout(layout).eligible);
   layout.selected_tile_count=16;
   layout.usable_gmem=0;
   assert(!frane_2634_eval_layout(layout).eligible);
   for (bool prefer_sysmem : {false,true}) {
      frane_26364_state state {};
      for (uint32_t o=1; o<=128; ++o)
         frane_26364_feed(state, o%2, (bool(o%2)==prefer_sysmem)?100:300,o);
      auto word=frane_26364_pack(state);
      unsigned owned=0, probes=0;
      for (uint32_t o=129; o<257; ++o) {
         const auto choice=frane_26364_select(true,false,word,50,o,12345,true);
         if (choice.owns) {
            ++owned;
            probes+=choice.measure;
            if (!choice.measure) assert(choice.sysmem==prefer_sysmem);
         }
      }
      assert(owned==128 && probes<32);
   }
   auto key=frane_switch_area_key(0,0,1280,720,20,1);
   assert(key==frane_switch_area_key(0,0,1280,720,63,1));
   assert(key!=frane_switch_area_key(0,0,640,360,20,1));
   assert(key!=frane_switch_area_key(1,0,1280,720,20,1));
   assert(key!=frane_switch_area_key(0,1,1280,720,20,1));
   assert(key!=frane_switch_area_key(0,0,1280,720,64,1));
   assert(key!=frane_switch_area_key(0,0,1280,720,20,2));
   for (uint32_t d=0;d<5;d++) assert(frane_switch_draw_band(d)==d);
   assert(frane_switch_draw_band(5)==5 && frane_switch_draw_band(15)==5);
   assert(frane_switch_draw_band(16)==6 && frane_switch_draw_band(63)==6);
   assert(frane_switch_draw_band(64)==7 && frane_switch_draw_band(255)==7);
   assert(frane_switch_draw_band(256)==8 && frane_switch_draw_band(UINT32_MAX)==8);
   assert(frane_switch_area_key(-1,-2,1,1,1,1)[0]==UINT32_MAX);
   printf("PASS Switch policy: %u boundary cases; area/offset/draw-band/subpass isolation.\n",cases);
}
