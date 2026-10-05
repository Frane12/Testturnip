#ifndef FRANE_S3_ORCHESTRATOR_H
#define FRANE_S3_ORCHESTRATOR_H
#include <algorithm>
#include <cstdint>
#include "frane_mesa_2634_a810_gmem_runtime.h"

struct frane_s3_config {
   bool enabled = true;
   uint32_t policy = 1;
   uint32_t cold_log2 = 4;
   uint32_t warm_log2 = 6;
   uint32_t hot_log2 = 9;
   uint32_t sentinel_log2 = 8;
   uint32_t min_pairs = 6;
   uint32_t gain = 25;
   uint32_t risk = 100;
   uint32_t ema_shift = 2;
   uint32_t drift = 300;
   uint32_t drift_hits = 2;
   uint32_t max_age = 2048;
   uint32_t max_tiles = 64;
   uint32_t min_ticks = 154;
};

static inline frane_s3_config frane_s3_normalize(frane_s3_config c) {
   c.policy = std::min(c.policy, 3u);
   c.cold_log2 = std::clamp(c.cold_log2, 3u, 6u);
   c.warm_log2 = std::clamp(c.warm_log2, c.cold_log2, 9u);
   c.hot_log2 = std::clamp(c.hot_log2, c.warm_log2, 10u);
   c.sentinel_log2 = std::clamp(c.sentinel_log2, 4u, 10u);
   c.min_pairs = std::clamp(c.min_pairs, 4u, 16u);
   c.gain = std::clamp(c.gain, 5u, 250u);
   c.risk = std::min(c.risk, 400u);
   c.ema_shift = std::clamp(c.ema_shift, 1u, 5u);
   c.drift = std::clamp(c.drift, 100u, 1000u);
   c.drift_hits = std::clamp(c.drift_hits, 1u, 4u);
   c.max_age = std::clamp(c.max_age, 2u << c.hot_log2, 65536u);
   c.max_tiles = std::clamp(c.max_tiles, 8u, 128u);
   c.min_ticks = std::min(c.min_ticks, 19200u);
   return c;
}

static inline bool frane_s3_eligible(const frane_2634_gmem_layout_input &l,
                                    const frane_s3_config &c) {
   if (l.physical_gmem < 262144 || l.physical_gmem > 2097152 ||
       l.usable_gmem < 65536 || l.usable_gmem > l.physical_gmem ||
       l.pixels_per_tile < 16 || !l.pass_pixels ||
       l.pass_pixels > 2073600 || l.drawcalls < 5)
      return false;
   const uint64_t pixels = l.pixels_per_tile-l.pixels_per_tile/16;
   const uint64_t tiles = l.selected_tile_count ? l.selected_tile_count :
      l.pass_pixels/pixels + bool(l.pass_pixels%pixels);
   return tiles && tiles <= c.max_tiles;
}

struct frane_s3_state {
   uint64_t cost[2] {};
   uint64_t mean_cost[2] {};
   uint32_t tag = 0;
   uint32_t completed_tag = 0;
   uint32_t stamp = 0;
   uint32_t last_seen[2] {};
   uint32_t pairs = 0;
   uint32_t resets = 0;
   int32_t mean = 0;
   int32_t deviation = 0;
   uint8_t pending = 0;
   uint8_t opposite = 0;
   uint8_t drift_count = 0;
   bool completed = false;
   bool trusted = false;
   bool sysmem = false;
   bool tiny = false;
};

struct frane_s3_decision {
   bool owns = false;
   bool sysmem = false;
   bool measure = false;
   bool paired = false;
   uint32_t tag = 0;
   uint8_t tier = 0;
};

static inline uint32_t frane_s3_ratio(uint64_t a, uint64_t b) {
   return b ? uint32_t(std::min<__uint128_t>(1000,
      __uint128_t(a)*1000/b)) : 0;
}

static inline uint64_t frane_s3_average(uint64_t a, uint64_t b, uint32_t shift) {
   if (!a) return b;
   return b >= a ? a+((b-a)>>shift) : a-((a-b)>>shift);
}

static inline uint64_t frane_s3_pack(const frane_s3_state &s,
                                   const frane_s3_config &c) {
   const uint32_t tier = !s.trusted ? 0 : s.pairs >= std::max(16u,c.min_pairs) ? 3 :
      s.pairs >= std::max(12u,c.min_pairs) ? 2 : 1;
   return (uint64_t(s.stamp)<<32) | uint32_t(s.sysmem) |
      (uint32_t(s.trusted)<<1) | (tier<<2) | (uint32_t(s.tiny)<<4);
}

static inline uint32_t frane_s3_mix(uint32_t x) {
   x ^= x>>16; x *= UINT32_C(0x7feb352d);
   x ^= x>>15; x *= UINT32_C(0x846ca68b); return x^(x>>16);
}

static inline frane_s3_decision frane_s3_select(const frane_s3_config &c,
   bool tail, uint64_t word, uint32_t probability, uint32_t occurrence,
   uint64_t hash) {
   frane_s3_decision d {};
   if (!c.enabled || !c.policy) return d;
   const bool fresh = uint32_t(occurrence-uint32_t(word>>32)) <= c.max_age;
   const bool trusted = fresh && bool(word&2);
   const bool tiny = fresh && bool(word&16);
   const uint32_t tier = trusted ? uint32_t((word>>2)&3) : 0;
   uint32_t shift = tier==3 ? c.hot_log2 : tier==2 ?
      std::min(c.hot_log2,c.warm_log2+1) : tier ? c.warm_log2 :
      tiny ? c.hot_log2 : c.cold_log2;
   if (tail && trusted) shift=std::max(c.cold_log2,shift-1);
   const uint32_t mask=(1u<<shift)-1;
   const uint32_t seed=uint32_t(hash)^uint32_t(hash>>32);
   uint32_t slot=frane_s3_mix((occurrence>>shift)^seed)&mask;
   if (slot==mask) --slot;
   const uint32_t phase=occurrence&mask;
   const bool first=phase==slot;
   const bool second=phase==slot+1;
   d.owns=true;
   d.tier=uint8_t(tier);
   d.sysmem=trusted ? bool(word&1) : probability>=50;
   d.paired=first||second;
   d.tag=(occurrence&~mask)+slot;
   if (second) d.sysmem=!d.sysmem;
   d.measure=d.paired;
   if (trusted && !d.paired) {
      const uint32_t smask=(1u<<c.sentinel_log2)-1;
      const uint32_t sslot=frane_s3_mix((occurrence>>c.sentinel_log2)^seed^
                                     UINT32_C(0xa511e9b3))&smask;
      d.measure=(occurrence&smask)==sslot;
   }
   return d;
}

static inline void frane_s3_feed(frane_s3_state &s, const frane_s3_config &c,
   bool sysmem, uint64_t duration, uint32_t occurrence, bool paired, uint32_t tag) {
   if (!duration || !c.enabled || !c.policy) return;
   const uint32_t mode=uint32_t(sysmem);
   if (s.mean_cost[mode] &&
       uint32_t(occurrence-s.last_seen[mode])>=UINT32_C(0x80000000)) return;
   s.last_seen[mode]=occurrence;
   if (!paired && s.trusted && sysmem==s.sysmem && s.mean_cost[mode]) {
      const uint64_t ref=s.mean_cost[mode];
      const uint64_t delta=duration>ref ? duration-ref : ref-duration;
      const uint32_t change=frane_s3_ratio(delta,std::max(duration,ref));
      s.drift_count=change>=c.drift ? uint8_t(s.drift_count+1) : 0;
      if (s.drift_count>=c.drift_hits) {
         s.trusted=false; s.tiny=false; s.pairs=0; s.mean=0; s.deviation=0;
         s.pending=0; s.opposite=0; s.drift_count=0; s.stamp=occurrence;
         s.completed=true; s.completed_tag=occurrence;
         if (s.resets!=UINT32_MAX) ++s.resets;
      }
   }
   if (!s.drift_count)
      s.mean_cost[mode]=frane_s3_average(s.mean_cost[mode],duration,c.ema_shift);
   if (!paired) return;
   if (s.completed &&
       (tag==s.completed_tag || uint32_t(tag-s.completed_tag)>=UINT32_C(0x80000000)))
      return;
   if (s.pending && tag!=s.tag) {
      if (uint32_t(tag-s.tag)>=UINT32_C(0x80000000)) return;
      s.pending=0;
   }
   s.tag=tag;
   s.cost[mode]=duration;
   s.pending|=uint8_t(1u<<mode);
   if (s.pending!=3) return;
   s.pending=0; s.completed=true; s.completed_tag=tag; s.stamp=tag+1;
   const uint64_t g=s.cost[0], y=s.cost[1], high=std::max(g,y);
   const int32_t advantage=g>=y ? int32_t(frane_s3_ratio(g-y,high)) :
                                 -int32_t(frane_s3_ratio(y-g,high));
   const int32_t magnitude=advantage<0 ? -advantage : advantage;
   const bool fresh_sys=advantage>0;
   if (s.trusted && fresh_sys!=s.sysmem && magnitude>=int32_t(c.gain*2)) {
      if (++s.opposite>=2) {
         s.pairs=0; s.mean=0; s.deviation=0; s.trusted=false; s.opposite=0;
      }
   } else s.opposite=0;
   if (!s.pairs) { s.mean=advantage; s.deviation=0; }
   else {
      const int32_t diff=advantage-s.mean;
      const int32_t residual=diff<0 ? -diff : diff;
      s.mean+=diff/int32_t(1u<<c.ema_shift);
      s.deviation+=(residual-s.deviation)/int32_t(1u<<c.ema_shift);
   }
   if (s.pairs!=UINT32_MAX) ++s.pairs;
   s.tiny=high<c.min_ticks;
   const int32_t margin=s.mean<0 ? -s.mean : s.mean;
   const int32_t hurdle=int32_t(c.gain)+s.deviation*int32_t(c.risk)/100;
   s.trusted=!s.tiny && s.pairs>=c.min_pairs && margin>hurdle;
   if (s.trusted) s.sysmem=s.mean>0;
}
#endif
