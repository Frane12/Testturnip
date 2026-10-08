/* SPDX-License-Identifier: MIT
 * Drnas-Turnip A810 / S1 AT2: low-overhead hysteresis overlay for AT1.
 *
 * This layer never changes attachment layout, barriers, synchronization,
 * renderpass correctness, or query allocation. Update on the AT1 submit
 * thread; read a packed atomic snapshot on recording threads.
 */
#ifndef FRANE_S1AT2_HYSTERESIS_H
#define FRANE_S1AT2_HYSTERESIS_H

#include <algorithm>
#include <cstdint>

struct frane_s1at2_state {
   uint16_t signature = 0;
   int8_t direction = 0; /* +1 GMEM, -1 SYSMEM, 0 neutral */
   int8_t candidate = 0;
   uint8_t candidate_streak = 0;
   uint8_t strength = 0; /* percentage-point overlay 0..5 */
};

struct frane_s1at2_snapshot {
   uint16_t signature = 0;
   int8_t direction = 0;
   uint8_t strength = 0;
};

struct frane_s1at2_input {
   bool at1_override = false;
   bool at1_select_sysmem = false;
   bool at1_force_measure = false;
   uint32_t at1_effective_sysmem_probability = 50;
   uint16_t signature = 0;
   uint64_t decision_word = 0;
   frane_s1at2_snapshot learned {};
};

struct frane_s1at2_decision {
   bool select_sysmem = false;
   bool force_measure = false;
   bool changed = false;
   uint32_t effective_sysmem_probability = 50;
};

static inline frane_s1at2_state
frane_s1at2_update_state(frane_s1at2_state s, int at1_score,
                         uint8_t at1_volatility, uint16_t signature,
                         uint16_t sysmem_samples, uint16_t gmem_samples)
{
   if (!signature)
      return s;

   if (s.signature != signature) {
      /* Do not drag preference from an unrelated RP signature. */
      s = {};
      s.signature = signature;
   }

   /* AT1's regime detector owns the fast-change signal. A volatile
    * signature must return promptly to the exact AT1 policy.
    */
   if (at1_volatility >= 8) {
      s.direction = 0;
      s.candidate = 0;
      s.candidate_streak = 0;
      s.strength = 0;
      return s;
   }

   const uint16_t paired = std::min(sysmem_samples, gmem_samples);
   const int candidate = paired < 8 || at1_volatility >= 6 ? 0 :
                         at1_score >= 6 ? 1 : at1_score <= -6 ? -1 : 0;
   if (candidate == 0) {
      s.candidate = 0;
      s.candidate_streak = 0;
      if (s.strength)
         s.strength--;
      if (!s.strength)
         s.direction = 0;
      return s;
   }

   if (candidate == s.direction) {
      s.candidate = 0;
      s.candidate_streak = 0;
      if (paired >= 16 && at1_volatility <= 3 &&
          (at1_score >= 10 || at1_score <= -10) && s.strength < 5)
         s.strength++;
      return s;
   }

   if (candidate != s.candidate) {
      s.candidate = int8_t(candidate);
      s.candidate_streak = 1;
   } else if (s.candidate_streak < 255) {
      s.candidate_streak++;
   }

   /* Switching an established preference needs stronger evidence than
    * establishing the first preference. Counts are GPU measurements, not
    * frames, so the main recording hot path remains cheap.
    */
   const uint8_t required = s.direction ? 5 : 3;
   if (s.candidate_streak >= required) {
      s.direction = int8_t(candidate);
      s.strength = 1;
      s.candidate = 0;
      s.candidate_streak = 0;
   } else if (s.strength) {
      s.strength--; /* contradictory evidence removes old authority */
   }
   return s;
}

static inline uint32_t
frane_s1at2_pack(frane_s1at2_state s)
{
   const uint32_t d = s.direction == 1 ? 1u : s.direction == -1 ? 2u : 0u;
   return uint32_t(s.signature) | (d << 16) |
          (uint32_t(std::min<unsigned>(5u, s.strength)) << 18);
}

static inline frane_s1at2_snapshot
frane_s1at2_unpack(uint32_t word)
{
   frane_s1at2_snapshot s {};
   s.signature = uint16_t(word & 0xffffu);
   const uint32_t d = (word >> 16) & 3u;
   s.direction = d == 1u ? 1 : d == 2u ? -1 : 0;
   s.strength = uint8_t(std::min<uint32_t>(5u, (word >> 18) & 7u));
   return s;
}

static inline frane_s1at2_decision
frane_s1at2_decide(const frane_s1at2_input &in)
{
   frane_s1at2_decision out {};
   out.select_sysmem = in.at1_select_sysmem;
   out.force_measure = in.at1_force_measure;
   out.effective_sysmem_probability = in.at1_effective_sysmem_probability;

   /* Never intercept AT1's exploration (including loser verification).
    * If AT1 did not override, leave the exact AT1/S1 choice untouched.
    */
   if (!in.at1_override || in.at1_force_measure || !in.signature ||
       in.learned.signature != in.signature ||
       !in.learned.direction || !in.learned.strength)
      return out;

   const int base = int(std::min<uint32_t>(100u,
                                         in.at1_effective_sysmem_probability));
   const int bias = -int(in.learned.direction) *
                    int(std::min<unsigned>(5u, in.learned.strength));
   const int adjusted = std::clamp(base + bias, 4, 96);
   out.effective_sysmem_probability = uint32_t(adjusted);
   out.select_sysmem = (in.decision_word % 100u) < uint64_t(adjusted);
   out.changed = adjusted != base;
   return out;
}

#endif
