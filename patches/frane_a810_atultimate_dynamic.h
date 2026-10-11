/* SPDX-License-Identifier: MIT
 * ATUltimate Dynamic V2 A810: per-render-pass category hysteresis and measured
 * GPU winner. One existing AT3 16-way associative GPU timestamp table is the
 * ONLY timing authority. No AT9, no forced SYSMEM, no new query/heap/lock.
 */
#ifndef FRANE_A810_ATULTIMATE_DYNAMIC_H
#define FRANE_A810_ATULTIMATE_DYNAMIC_H
#include "frane_a810_atultimate.h"
#include <atomic>
#include <algorithm>
#include <cstdint>
#include <cstdlib>

struct frane_atu_dyn_state {
   uint16_t active = 0;
   uint16_t pending = 0;
   uint8_t hits = 0;       /* consecutive render contexts for new category */
   uint8_t winner = 0;     /* 0 unknown, 1 GMEM, 2 SYSMEM */
   uint8_t votes = 0;      /* consecutive proof of new measured winner */
   uint8_t cooldown = 0;   /* minimum intervening decisions after activation */
};
static inline uint64_t frane_atu_dyn_pack(frane_atu_dyn_state s)
{
   return uint64_t(s.active) | (uint64_t(s.pending) << 16) |
      (uint64_t(s.hits & 15u) << 32) | (uint64_t(s.winner & 3u) << 36) |
      (uint64_t(s.votes & 15u) << 38) | (uint64_t(s.cooldown & 63u) << 42);
}
static inline frane_atu_dyn_state frane_atu_dyn_unpack(uint64_t w)
{
   frane_atu_dyn_state s {};
   s.active = uint16_t(w); s.pending = uint16_t(w >> 16);
   s.hits = uint8_t((w >> 32) & 15u);
   s.winner = uint8_t((w >> 36) & 3u);
   s.votes = uint8_t((w >> 38) & 15u);
   s.cooldown = uint8_t((w >> 42) & 63u);
   return s;
}

struct frane_atu_dyn_result {
   frane_s1at1_decision decision {};
   frane_atu_dyn_state state {};
   bool phase_switch = false;
   bool winner_switch = false;
   bool waiting = false;
   bool used = false;
   bool confident = false;
   uint8_t category = 0;
};

/* No special-case game/hash. "Fast" must clear the AT8-level two-pair GPU
 * confidence test. Moderate asks >=3 per-mode completed GPU timestamps.
 * Do not trust timestamps for stale, volatile, mismatched or tiny passes.
 */
static inline uint8_t
frane_atu_dyn_candidate(const frane_s1at1_context_input &in,
                        const frane_s1at3_snapshot &s,
                        bool fast_mode, uint8_t *required_votes = nullptr)
{
   const auto cat = frane_s1at1_catalog_for(in);
   if (!cat.signature || s.signature != cat.signature ||
       in.occurrences < 4 || in.estimated_tiles == 0 ||
       in.estimated_tiles > 24 || in.drawcalls < 5 ||
       s.stale[0] || s.stale[1])
      return 0;
   const unsigned pairs = std::min(s.samples[0],s.samples[1]);
   const unsigned confidence = std::abs(int(s.score));
   const bool fast = fast_mode && pairs >= 2 &&
      confidence >= 20 && s.at7_saving_4us >= 150 &&
      s.at7_noise_q8 <= 24 && s.volatility == 0;
   const bool normal = pairs >= 3 && confidence >= 10 &&
      s.at7_saving_4us >= 45 && s.at7_noise_q8 <= 72 &&
      s.volatility <= 2;
   if (!fast && !normal)
      return 0;
   if (required_votes) *required_votes = fast ? 2u : 4u;
   return s.score < 0 ? 2u : 1u;
}

/* Thread-safe per-RP context switcher. Three repeated class observations
 * (not mere draw fluctuations) before active phase changes. GPU winner must
 * prove itself for 2/4 decisions to acquire, and for 5/7 to reverse,
 * plus 24-decision dwell after any change. A stable champion uses only
 * one relaxed atomic LOAD; even its cooldown is not refreshed.
 *
 * 'may_override' only allows the final action. AT4 measurement requests
 * and other existing policies remain authoritative; phase observation runs.
 */
static inline frane_atu_dyn_result
frane_atu_dyn_step(std::atomic<uint64_t> &word,
                    const frane_s1at1_context_input &in,
                    const frane_s1at3_snapshot &snapshot,
                    bool may_override, bool fast_mode = true,
                    unsigned stable_hits = 3u,
                    unsigned dwell = 24u)
{
   frane_atu_dyn_result out {};
   const auto cat = frane_s1at1_catalog_for(in);
   out.category = uint8_t(cat.id);
   const uint16_t signature = cat.signature;
   if (!signature || in.estimated_tiles == 0 ||
       in.estimated_tiles > 24 || in.drawcalls < 5)
      return out;
   stable_hits = std::clamp(stable_hits, 2u, 8u);
   dwell = std::clamp(dwell, 8u, 48u);
   uint8_t required=0;
   const uint8_t candidate = frane_atu_dyn_candidate(
      in,snapshot,fast_mode,&required);
   out.confident = candidate != 0;
   for(unsigned trial=0;trial<4;trial++) {
      uint64_t old=word.load(std::memory_order_relaxed);
      auto s=frane_atu_dyn_unpack(old);
      auto n=s;
      bool new_phase=false,new_winner=false;
      if (s.active != signature) {
         if (s.pending == signature)
            n.hits = std::min<unsigned>(15u,unsigned(s.hits)+1u);
         else {
            n.pending = signature;
            n.hits = 1;
         }
         if (n.hits >= stable_hits) {
            n.active = signature;
            n.pending = 0;
            n.hits = 0;
            n.winner = 0;
            n.votes = 0;
            n.cooldown = 0;
            new_phase=true;
         }
      } else {
         n.pending=0; n.hits=0;
         if (!candidate) {
            n.votes=0;  /* measured proof lost: do not use latched winner */
         } else if (!s.winner) {
            n.votes = std::min<unsigned>(15,unsigned(s.votes)+1u);
            if (n.votes >= required) {
               n.winner = candidate;
               n.votes = 0;
               n.cooldown = uint8_t(dwell);
               new_winner=true;
            }
         } else if (candidate == s.winner) {
            n.votes = 0;
            if (n.cooldown) --n.cooldown;
         } else {
            if (n.cooldown) {
               --n.cooldown;
               n.votes=0;
            } else {
               n.votes = std::min<unsigned>(15,unsigned(s.votes)+1u);
               if (n.votes >= required+3u) {
                  n.winner=candidate;
                  n.votes=0;
                  n.cooldown=uint8_t(dwell);
                  new_winner=true;
               }
            }
         }
      }
      const bool changed=frane_atu_dyn_pack(n)!=old;
      if (changed && !word.compare_exchange_weak(
            old,frane_atu_dyn_pack(n),std::memory_order_relaxed,
            std::memory_order_relaxed))
         continue;
      out.state=n;out.phase_switch=new_phase;out.winner_switch=new_winner;
      out.waiting=n.active!=signature || n.winner==0 ||
         (n.winner!=candidate && candidate!=0);
      /* Never select on a different context, a stale GPU champion, or
       * an unproven challenger. Existing AT4 probes can override this. */
      if (may_override && n.active==signature &&
          candidate && n.winner==candidate) {
         out.decision.override_mode=true;
         out.decision.select_sysmem=candidate==2;
         out.decision.effective_sysmem_probability=candidate==2?100u:0u;
         out.decision.signature=signature;
         out.decision.catalog_id=out.category;
         out.decision.confidence=uint8_t(std::abs(int(snapshot.score)));
         out.used=true;
      }
      return out;
   }
   return out; /* Concurrent contention: abstain, preserve legacy decision. */
}
#endif
