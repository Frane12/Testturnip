#include <cassert>
#include <cstdio>
#include <set>
#include <limits>
#include "frane_ds1.h"
#include "frane_mesa_26364_a810_smart_v2.h"

int main()
{
   unsigned cases = 0;
   for (auto kind : {FRANE_DS1_DEPTH, FRANE_DS1_PACKED, FRANE_DS1_SPLIT, FRANE_DS1_STENCIL}) {
      std::set<uint32_t> keys;
      const unsigned aspects = frane_ds1_aspects(kind);
      for (unsigned load = 0; load < 4; ++load)
      for (unsigned store = 0; store < 4; ++store)
      for (unsigned clear = 0; clear < 4; ++clear)
      for (unsigned preserve = 0; preserve < 4; ++preserve) {
         frane_ds1_ops op {uint8_t(load), uint8_t(store), uint8_t(clear), uint8_t(preserve), true};
         const bool legal = !((load | store | clear | preserve) & ~aspects) &&
                            !(load & clear) && !(store & preserve);
         frane_ds1_emitted e {};
         e.clear = clear;
         if (kind == FRANE_DS1_SPLIT) {
            e.load = load & 1; e.store = store & 1;
            e.load_stencil = load & 2; e.store_stencil = store & 2;
         } else {
            e.load = load || (kind == FRANE_DS1_PACKED && store && preserve);
            e.store = store;
         }
         assert(frane_ds1_ops_valid(kind, op, e) == legal);
         assert(keys.insert(frane_ds1_ops_key(kind, op)).second);
         if (legal) {
            auto broken = e; broken.load = !broken.load;
            assert(!frane_ds1_ops_valid(kind, op, broken));
            broken = e; broken.store = !broken.store;
            assert(!frane_ds1_ops_valid(kind, op, broken));
            broken = e; broken.load_stencil = !broken.load_stencil;
            assert(!frane_ds1_ops_valid(kind, op, broken));
            broken = e; broken.store_stencil = !broken.store_stencil;
            assert(!frane_ds1_ops_valid(kind, op, broken));
            broken = e; broken.clear ^= 1;
            assert(!frane_ds1_ops_valid(kind, op, broken));
            op.known = false;
            assert(!frane_ds1_ops_valid(kind, op, e));
         }
         ++cases;
      }
   }
   frane_ds1_ops passthrough {0, 1, 0, 2, true};
   assert(!frane_ds1_ops_valid(FRANE_DS1_PACKED, passthrough, {false,true,false,false,0}));
   assert(frane_ds1_ops_valid(FRANE_DS1_PACKED, passthrough, {true,true,false,false,0}));
   frane_ds1_plane planes[8] {{0,4},{65536,1}};
   assert(frane_ds1_planes_valid(planes,2,16384,81920,4096));
   planes[1].offset = 61440;
   assert(!frane_ds1_planes_valid(planes,2,16384,81920,4096));
   planes[1].offset = 65536;
   assert(!frane_ds1_planes_valid(planes,2,16384,81919,4096));
   assert(!frane_ds1_planes_valid(planes,2,0,81920,4096));
   assert(!frane_ds1_planes_valid(planes,2,UINT32_MAX,UINT32_MAX,4096));
   assert(!frane_ds1_planes_valid(planes,9,1,81920,4096));
   assert(!frane_ds1_planes_valid(nullptr,2,16384,81920,4096));
   for (uint32_t offset=0;offset<65536;offset+=256) {
      for (uint32_t pixels=1;pixels<20000;pixels+=137) {
         planes[1] = {int32_t(offset),1};
         const uint64_t e0 = uint64_t(pixels)*4;
         const uint64_t e1 = uint64_t(offset)+pixels;
         const bool expected = offset%4096==0 && e0<=81920 && e1<=81920 && offset>=e0;
         assert(frane_ds1_planes_valid(planes,2,pixels,81920,4096)==expected);
         ++cases;
      }
   }
   for (bool enabled : {false,true})
   for (bool owned : {false,true})
   for (bool measured : {false,true})
   for (uint8_t flags=0;flags<32;++flags) {
      const bool allowed=frane_ds1_frontier_allowed(enabled,owned,measured,flags);
      if (enabled && (owned || measured || (flags & FRANE_DS1_HAS_STENCIL))) assert(!allowed);
      if (!enabled) assert(allowed);
      ++cases;
   }
   for (bool prefer_sys : {false,true}) {
      frane_26364_state st {};
      for (unsigned i=0;i<16;++i) {
         frane_26364_feed(st,false,prefer_sys?200:100,i*8);
         frane_26364_feed(st,true,prefer_sys?100:200,i*8+1);
      }
      unsigned measures=0,losers=0;
      for (unsigned occurrence=256;occurrence<512;++occurrence) {
         const auto d=frane_26364_select(true,true,frane_26364_pack(st),prefer_sys?80:20,occurrence,123);
         assert(d.owns && d.tier==3);
         assert(!frane_ds1_frontier_allowed(true,d.owns,d.measure,FRANE_DS1_HAS_DEPTH));
         measures+=d.measure;losers+=d.sysmem!=prefer_sys;
      }
      assert(measures==2 && losers==1);
   }
   std::printf("DS1 ops, geometry, signatures and Smart ownership: %u cases PASS\n",cases);
}
