/* SPDX-License-Identifier: MIT
 * ATUltimate Dynamic V3: 4-entry category-aware champion cache per RP.
 * Existing AT3 16-entry, GPU-timed history is the sole timing authority.
 * Each cached winner MUST be revalidated against fresh, matching AT3 data.
 * AT4 exploration and downstream GMEM correctness gates always win.
 */
#ifndef FRANE_A810_ATULTIMATE_V3_H
#define FRANE_A810_ATULTIMATE_V3_H
#include "frane_a810_atultimate_dynamic.h"
#include <algorithm>
#include <atomic>
#include <cstdint>

#define FRANE_ATU_V3_SLOTS 4

enum frane_atu_v3_why : uint8_t {
   ATU_V3_OFF = 0,
   ATU_V3_NO_CONTEXT,
   ATU_V3_PHASE_WAIT,
   ATU_V3_CACHE_NEW,
   ATU_V3_CACHE_BUSY,
   ATU_V3_NO_HISTORY,
   ATU_V3_STALE_HISTORY,
   ATU_V3_NO_PAIRED,
   ATU_V3_NOISY_HISTORY,
   ATU_V3_WAIT_VOTES,
   ATU_V3_WAIT_DWELL,
   ATU_V3_WINNER_CONFLICT,
   ATU_V3_AT4_PROBE,
   ATU_V3_AT4_PRIORITY,
   ATU_V3_RUNTIME_PRIORITY,
   ATU_V3_READY,
   ATU_V3_USED,
};
static inline const char *frane_atu_v3_reason(frane_atu_v3_why v)
{
   switch (v) {
   case ATU_V3_NO_CONTEXT: return "NO_CONTEXT";
   case ATU_V3_PHASE_WAIT: return "PHASE_WAIT";
   case ATU_V3_CACHE_NEW: return "CACHE_NEW";
   case ATU_V3_CACHE_BUSY: return "CACHE_BUSY";
   case ATU_V3_NO_HISTORY: return "NO_HISTORY";
   case ATU_V3_STALE_HISTORY: return "STALE_HISTORY";
   case ATU_V3_NO_PAIRED: return "NO_PAIRED";
   case ATU_V3_NOISY_HISTORY: return "NOISY_HISTORY";
   case ATU_V3_WAIT_VOTES: return "WAIT_VOTES";
   case ATU_V3_WAIT_DWELL: return "WAIT_DWELL";
   case ATU_V3_WINNER_CONFLICT: return "WINNER_CONFLICT";
   case ATU_V3_AT4_PROBE: return "AT4_PROBE";
   case ATU_V3_AT4_PRIORITY: return "AT4_PRIORITY";
   case ATU_V3_RUNTIME_PRIORITY: return "RUNTIME_PRIORITY";
   case ATU_V3_READY: return "READY";
   case ATU_V3_USED: return "USED";
   default: return "OFF";
   }
}
struct frane_atu_v3_slot {
   uint16_t key = 0;
   uint8_t winner = 0;        /* 1=GMEM, 2=SYSMEM */
   uint8_t challenger = 0;    /* tracks vote DIRECTION across frames */
   uint8_t votes = 0;
   uint8_t dwell = 0;
   uint8_t frequency = 0;
   uint8_t last_epoch = 0;    /* approximate LRU, rolls over at 256 */
};
static inline uint64_t frane_atu_v3_pack(frane_atu_v3_slot s)
{
   return uint64_t(s.key) | (uint64_t(s.winner & 3u) << 16) |
      (uint64_t(s.challenger & 3u) << 18) |
      (uint64_t(s.votes & 15u) << 20) |
      (uint64_t(s.dwell & 63u) << 24) |
      (uint64_t(s.frequency) << 30) |
      (uint64_t(s.last_epoch) << 38);
}
static inline frane_atu_v3_slot frane_atu_v3_unpack(uint64_t v)
{
   frane_atu_v3_slot s {};
   s.key = uint16_t(v);
   s.winner = uint8_t((v >> 16) & 3u);
   s.challenger = uint8_t((v >> 18) & 3u);
   s.votes = uint8_t((v >> 20) & 15u);
   s.dwell = uint8_t((v >> 24) & 63u);
   s.frequency = uint8_t((v >> 30) & 255u);
   s.last_epoch = uint8_t((v >> 38) & 255u);
   return s;
}
struct frane_atu_v3_result {
   frane_s1at1_decision decision {};
   frane_atu_v3_slot slot {};
   frane_atu_v3_why why = ATU_V3_OFF;
   uint16_t category_key = 0;
   uint8_t catalog = 0;
   uint8_t slot_id = 255;
   uint8_t candidate = 0;
   bool cache_hit = false;
   bool cache_evicted = false;
   bool phase_switched = false;
   bool winner_acquired = false;
   bool winner_changed = false;
   bool used = false;
   bool blocked = false;
   bool confident = false;
};

static inline frane_atu_v3_why
frane_atu_v3_no_candidate_why(const frane_s1at1_context_input &in,
                              const frane_s1at3_snapshot &s)
{
   auto cat = frane_s1at1_catalog_for(in);
   if (!cat.signature || cat.signature != s.signature)
      return ATU_V3_NO_HISTORY;
   if (s.stale[0] || s.stale[1])
      return ATU_V3_STALE_HISTORY;
   if (std::min(s.samples[0], s.samples[1]) < 2)
      return ATU_V3_NO_PAIRED;
   return ATU_V3_NOISY_HISTORY; /* GPU difference/noise not yet compelling */
}

/* Phase word is the existing V2 atomic, but V3 never inherits V2 winner.
 * Returning to a familiar cached class requires two matching observations,
 * a new class requires >=3. Alternating phases will never activate.
 */
static inline bool
frane_atu_v3_phase(std::atomic<uint64_t> &phase,
                   uint16_t signature, bool warm,
                   unsigned stable_hits, bool *switched)
{
   const unsigned required = warm ? 2u : std::clamp(stable_hits, 2u, 8u);
   for (unsigned i = 0; i < 4; ++i) {
      uint64_t old = phase.load(std::memory_order_relaxed);
      auto s = frane_atu_dyn_unpack(old);
      if (s.active == signature)
         return true;
      auto n = s;
      if (n.pending == signature)
         n.hits = uint8_t(std::min<unsigned>(15u, n.hits + 1u));
      else {
         n.pending = signature;
         n.hits = 1;
      }
      bool changed = false;
      if (n.hits >= required) {
         n.active = signature; n.pending = 0; n.hits = 0;
         /* Winner stays in the corresponding category slot, not here. */
         n.winner = 0; n.votes = 0; n.cooldown = 0;
         changed = true;
      }
      if (phase.compare_exchange_weak(old, frane_atu_dyn_pack(n),
            std::memory_order_relaxed, std::memory_order_relaxed)) {
         if (switched) *switched = changed;
         return changed;
      }
   }
   return false;
}

/* Frequency-based replacement with aging: high-use classes survive, but
 * cached entries that have not appeared for many decisions gradually decay.
 * Avoid cache heaps, map lookups and locks in the recording thread.
 */
static inline unsigned
frane_atu_v3_choose_slot(std::atomic<uint64_t> slots[FRANE_ATU_V3_SLOTS],
                         uint16_t key, uint8_t epoch, bool *hit)
{
   unsigned empty = FRANE_ATU_V3_SLOTS;
   unsigned victim = 0;
   int worst = 0x7fffffff;
   for(unsigned i = 0; i < FRANE_ATU_V3_SLOTS; ++i) {
      const auto s = frane_atu_v3_unpack(
         slots[i].load(std::memory_order_relaxed));
      if (s.key == key) {
         if (hit) *hit = true;
         return i;
      }
      if (!s.key && empty == FRANE_ATU_V3_SLOTS)
         empty = i;
      const unsigned age = uint8_t(epoch - s.last_epoch);
      const int priority = int(s.frequency / 4u) - int(age / 8u);
      if (priority < worst) {
         worst = priority;
         victim = i;
      }
   }
   if (hit) *hit = false;
   return empty != FRANE_ATU_V3_SLOTS ? empty : victim;
}

/* Called once per render-pass selection, before AT8/AT7/AT63. The existing
 * AT4 decision may veto an override, but cache/history observation continues.
 * Cache evidence alone is NEVER sufficient to select a render mode.
 */
static inline frane_atu_v3_result
frane_atu_v3_step(std::atomic<uint64_t> slots[FRANE_ATU_V3_SLOTS],
                  std::atomic<uint64_t> &phase,
                  std::atomic<uint32_t> &epoch_counter,
                  const frane_s1at1_context_input &in,
                  const frane_s1at3_snapshot &snapshot,
                  bool may_override, bool at4_probe,
                  bool runtime_override, bool fast_mode,
                  unsigned stable_hits, unsigned dwell)
{
   frane_atu_v3_result out {};
   auto cat = frane_s1at1_catalog_for(in);
   out.catalog = uint8_t(cat.id);
   out.category_key = cat.signature;
   if (!cat.signature || !in.estimated_tiles ||
       in.estimated_tiles > 24 || in.drawcalls < 5) {
      out.why = ATU_V3_NO_CONTEXT;
      return out;
   }
   dwell = std::clamp(dwell, 8u, 48u);
   uint8_t required = 0;
   const uint8_t candidate = frane_atu_dyn_candidate(
      in, snapshot, fast_mode, &required);
   out.candidate = candidate;
   out.confident = candidate != 0;
   const uint8_t epoch = uint8_t(epoch_counter.fetch_add(
      1u, std::memory_order_relaxed) + 1u);
   bool hit = false;
   const unsigned index = frane_atu_v3_choose_slot(
      slots, cat.signature, epoch, &hit);
   out.slot_id = uint8_t(index);
   out.cache_hit = hit;

   /* Phase and cache are independent: a previously known class resumes its
    * old champion ONLY if new AT3 GPU evidence still confirms it.
    */
   const bool phase_ready = frane_atu_v3_phase(
      phase, cat.signature, hit, stable_hits, &out.phase_switched);

   for(unsigned attempt = 0; attempt < 4; ++attempt) {
      uint64_t old = slots[index].load(std::memory_order_relaxed);
      auto s = frane_atu_v3_unpack(old);
      auto n = s;
      if (s.key != cat.signature) {
         n = {};
         n.key = cat.signature;
         n.frequency = 1;
         n.last_epoch = epoch;
         if (s.key) out.cache_evicted = true;
      } else {
         const unsigned age = uint8_t(epoch - s.last_epoch);
         n.frequency = uint8_t(std::min<unsigned>(255u,
            unsigned(s.frequency > age / 16u ?
               s.frequency - age / 16u : 0u) + 1u));
         n.last_epoch = epoch;
      }
      if (!candidate) {
         /* Do not enforce stale winners; preserve category popularity. */
         n.challenger = 0;
         n.votes = 0;
      } else if (n.winner == candidate) {
         n.challenger = 0;
         n.votes = 0;
         if (n.dwell) --n.dwell;
      } else if (n.winner && n.dwell) {
         --n.dwell;
         n.challenger = 0;
         n.votes = 0;
      } else {
         if (n.challenger != candidate) {
            n.challenger = candidate;
            n.votes = 1;
         } else {
            n.votes = uint8_t(std::min<unsigned>(15u, n.votes + 1u));
         }
         const unsigned threshold = required + (n.winner ? 3u : 0u);
         if (n.votes >= threshold) {
            out.winner_changed = n.winner != 0;
            out.winner_acquired = true;
            n.winner = candidate;
            n.challenger = 0;
            n.votes = 0;
            n.dwell = uint8_t(dwell);
         }
      }
      if (!slots[index].compare_exchange_weak(
         old, frane_atu_v3_pack(n),
         std::memory_order_relaxed, std::memory_order_relaxed))
         continue;
      out.slot = n;
      if (!phase_ready)
         out.why = ATU_V3_PHASE_WAIT;
      else if (!candidate)
         out.why = frane_atu_v3_no_candidate_why(in, snapshot);
      else if (n.winner != candidate)
         out.why = n.dwell ? ATU_V3_WAIT_DWELL :
            (n.winner ? ATU_V3_WINNER_CONFLICT : ATU_V3_WAIT_VOTES);
      else if (!may_override) {
         out.blocked = true;
         out.why = at4_probe ? ATU_V3_AT4_PROBE :
            runtime_override ? ATU_V3_RUNTIME_PRIORITY : ATU_V3_AT4_PRIORITY;
      } else {
         out.decision.override_mode = true;
         out.decision.select_sysmem = candidate == 2;
         out.decision.effective_sysmem_probability =
            candidate == 2 ? 100u : 0u;
         out.decision.signature = cat.signature;
         out.decision.catalog_id = uint8_t(cat.id);
         out.decision.confidence =
            uint8_t(std::min(255, std::abs(int(snapshot.score))));
         out.used = true;
         out.why = ATU_V3_USED;
      }
      return out;
   }
   out.why = ATU_V3_CACHE_BUSY;
   return out;
}
#endif
