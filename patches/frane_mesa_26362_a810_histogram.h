/* SPDX-License-Identifier: MIT
 * Drnas-Turnip S1H A810 DECISION-HISTOGRAM / FRAMETIME-STABILIZER.
 *
 * Compact per-render-pass evidence histogram. It is fed only when a new
 * measured GMEM/SYSMEM pair becomes available. The histogram is recent-weighted
 * by periodically halving bins, so scene changes can replace old evidence.
 *
 * Histogram smoothing is deliberately conservative and optional:
 * - no allocation, locks, waits or loops with runtime-dependent bounds;
 * - never acts without measured paired evidence;
 * - strong contradictory learner / PROFILED evidence can veto it;
 * - sparse measured loser probes remain active for regime-change detection.
 */
#ifndef FRANE_MESA_26362_A810_HISTOGRAM_H
#define FRANE_MESA_26362_A810_HISTOGRAM_H

#include <cstdint>

#include "frane_mesa_26358_a810_tail_learner.h"

enum frane_26362_hist_bin : uint8_t {
   FRANE_HIST_GMEM_25 = 0,
   FRANE_HIST_GMEM_12,
   FRANE_HIST_GMEM_6,
   FRANE_HIST_TIE,
   FRANE_HIST_SYSMEM_6,
   FRANE_HIST_SYSMEM_12,
   FRANE_HIST_SYSMEM_25,
   FRANE_HIST_BIN_COUNT,
};

enum frane_26362_preference : int8_t {
   FRANE_HIST_PREF_GMEM = -1,
   FRANE_HIST_PREF_NONE = 0,
   FRANE_HIST_PREF_SYSMEM = 1,
};

struct frane_26362_hist_state {
   uint16_t bins[FRANE_HIST_BIN_COUNT] {};
   uint32_t observations = 0;
   uint16_t switches = 0;
   int8_t preference = FRANE_HIST_PREF_NONE;
   uint8_t confidence = 0; /* 0..8 */
};

struct frane_26362_hist_snapshot {
   int8_t preference = FRANE_HIST_PREF_NONE;
   uint8_t confidence = 0;
   uint8_t recent_observations = 0;
   uint16_t switches = 0;
};

struct frane_26362_hist_decision {
   bool override_mode = false;
   bool select_sysmem = false;
   bool force_measure = false;
   uint8_t confidence = 0;
   uint8_t probe_log2 = 0;
};

static inline uint32_t
frane_26362_recent_total(const frane_26362_hist_state &s)
{
   uint32_t total = 0;
   for (uint32_t i = 0; i < FRANE_HIST_BIN_COUNT; i++)
      total += s.bins[i];
   return total;
}

static inline frane_26362_hist_bin
frane_26362_classify(uint64_t sys_cost, uint64_t gm_cost)
{
   if (gm_cost && sys_cost) {
      if (frane_26358_ratio_le(gm_cost, sys_cost, 3, 4))
         return FRANE_HIST_GMEM_25;
      if (frane_26358_ratio_le(gm_cost, sys_cost, 7, 8))
         return FRANE_HIST_GMEM_12;
      if (frane_26358_ratio_le(gm_cost, sys_cost, 15, 16))
         return FRANE_HIST_GMEM_6;

      if (frane_26358_ratio_le(sys_cost, gm_cost, 3, 4))
         return FRANE_HIST_SYSMEM_25;
      if (frane_26358_ratio_le(sys_cost, gm_cost, 7, 8))
         return FRANE_HIST_SYSMEM_12;
      if (frane_26358_ratio_le(sys_cost, gm_cost, 15, 16))
         return FRANE_HIST_SYSMEM_6;
   }

   return FRANE_HIST_TIE;
}

static inline uint8_t
frane_26362_vote_confidence(const frane_26362_hist_state &s,
                            int8_t *candidate)
{
   const uint32_t gm_votes =
      uint32_t(s.bins[FRANE_HIST_GMEM_25]) * 3u +
      uint32_t(s.bins[FRANE_HIST_GMEM_12]) * 2u +
      uint32_t(s.bins[FRANE_HIST_GMEM_6]);
   const uint32_t sys_votes =
      uint32_t(s.bins[FRANE_HIST_SYSMEM_25]) * 3u +
      uint32_t(s.bins[FRANE_HIST_SYSMEM_12]) * 2u +
      uint32_t(s.bins[FRANE_HIST_SYSMEM_6]);

   const uint32_t votes = gm_votes + sys_votes;
   const uint32_t decisive =
      s.bins[FRANE_HIST_GMEM_25] + s.bins[FRANE_HIST_GMEM_12] +
      s.bins[FRANE_HIST_GMEM_6] + s.bins[FRANE_HIST_SYSMEM_6] +
      s.bins[FRANE_HIST_SYSMEM_12] + s.bins[FRANE_HIST_SYSMEM_25];

   *candidate = FRANE_HIST_PREF_NONE;
   if (votes == 0 || decisive < 6)
      return 0;

   const uint32_t margin =
      gm_votes > sys_votes ? gm_votes - sys_votes : sys_votes - gm_votes;
   uint32_t confidence = (margin * 8u + votes / 2u) / votes;
   if (confidence > 8)
      confidence = 8;

   if (confidence >= 4) {
      if (gm_votes > sys_votes)
         *candidate = FRANE_HIST_PREF_GMEM;
      else if (sys_votes > gm_votes)
         *candidate = FRANE_HIST_PREF_SYSMEM;
   }

   return uint8_t(confidence);
}

static inline frane_26362_hist_state
frane_26362_update_histogram(frane_26362_hist_state s,
                             uint64_t sys_cost,
                             uint64_t gm_cost)
{
   if (!sys_cost || !gm_cost)
      return s;

   /* Recent-weighted bounded histogram. When the window fills, halve every
    * bin. This retains long-term direction while letting a new scene replace
    * old evidence without storing individual frames.
    */
   if (frane_26362_recent_total(s) >= 64) {
      for (uint32_t i = 0; i < FRANE_HIST_BIN_COUNT; i++)
         s.bins[i] = uint16_t((uint32_t(s.bins[i]) + 1u) >> 1);
   }

   const auto bin = frane_26362_classify(sys_cost, gm_cost);
   if (s.bins[bin] != UINT16_MAX)
      s.bins[bin]++;
   if (s.observations != UINT32_MAX)
      s.observations++;

   int8_t candidate = FRANE_HIST_PREF_NONE;
   const uint8_t evidence_conf = frane_26362_vote_confidence(s, &candidate);
   const uint32_t total = frane_26362_recent_total(s);

   if (s.preference == FRANE_HIST_PREF_NONE) {
      if (candidate != FRANE_HIST_PREF_NONE && total >= 8) {
         s.preference = candidate;
         s.confidence = evidence_conf;
      } else if (s.confidence) {
         s.confidence--;
      }
      return s;
   }

   if (candidate == s.preference) {
      s.confidence = evidence_conf;
      return s;
   }

   if (candidate != FRANE_HIST_PREF_NONE &&
       candidate != s.preference &&
       total >= 12 && evidence_conf >= 6) {
      s.preference = candidate;
      s.confidence = evidence_conf;
      if (s.switches != UINT16_MAX)
         s.switches++;
      return s;
   }

   /* During a disputed transition, stop using the histogram as an override
    * before allowing it to flip. This is the frametime dead-band.
    */
   if (candidate != FRANE_HIST_PREF_NONE && candidate != s.preference) {
      s.confidence = evidence_conf >= 6 ? 0 : uint8_t(6 - evidence_conf);
      return s;
   }

   const uint32_t ties = s.bins[FRANE_HIST_TIE];
   if (total >= 16 && ties * 2u >= total && evidence_conf <= 1) {
      s.preference = FRANE_HIST_PREF_NONE;
      s.confidence = 0;
   } else if (s.confidence) {
      s.confidence--;
   }

   return s;
}

static inline uint32_t
frane_26362_pack_histogram(const frane_26362_hist_state &s)
{
   uint32_t pref = 0;
   if (s.preference == FRANE_HIST_PREF_GMEM)
      pref = 1;
   else if (s.preference == FRANE_HIST_PREF_SYSMEM)
      pref = 2;

   uint32_t confidence = s.confidence > 8 ? 8u : s.confidence;
   uint32_t recent = frane_26362_recent_total(s);
   if (recent > 127)
      recent = 127;
   const uint32_t switches = s.switches > 65535u ? 65535u : s.switches;

   return pref | (confidence << 2) | (recent << 6) | (switches << 16);
}

static inline frane_26362_hist_snapshot
frane_26362_unpack_histogram(uint32_t word)
{
   frane_26362_hist_snapshot out {};
   const uint32_t pref = word & 3u;
   if (pref == 1)
      out.preference = FRANE_HIST_PREF_GMEM;
   else if (pref == 2)
      out.preference = FRANE_HIST_PREF_SYSMEM;

   out.confidence = uint8_t((word >> 2) & 0xfu);
   if (out.confidence > 8)
      out.confidence = 8;
   out.recent_observations = uint8_t((word >> 6) & 0x7fu);
   out.switches = uint16_t(word >> 16);
   return out;
}

static inline frane_26362_hist_decision
frane_26362_decide_smoothing(bool enabled,
                             frane_26362_hist_snapshot hist,
                             frane_26358_tail_snapshot learned,
                             uint32_t sysmem_probability,
                             uint64_t decision_word)
{
   frane_26362_hist_decision out {};
   if (!enabled || hist.preference == FRANE_HIST_PREF_NONE ||
       hist.confidence < 4 || hist.recent_observations < 8)
      return out;

   const bool prefer_sys = hist.preference == FRANE_HIST_PREF_SYSMEM;
   const int learner_conf =
      learned.score < 0 ? -int(learned.score) : int(learned.score);
   const bool learner_pref_sys = learned.score < 0;

   /* A newly strong opposite learner means the workload has probably changed.
    * Stop smoothing immediately and let the newer evidence take control.
    */
   if (learned.ready && learner_conf >= 6 &&
       learned.score != 0 && learner_pref_sys != prefer_sys)
      return out;

   if (learned.ready && learner_conf >= 4 &&
       learned.score != 0 && learner_pref_sys != prefer_sys &&
       hist.confidence < 7)
      return out;

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   /* Respect a strong live PROFILED contradiction unless histogram consensus
    * is near-saturated.
    */
   if (!prefer_sys && sysmem_probability > 65 && hist.confidence < 7)
      return out;
   if (prefer_sys && sysmem_probability < 35 && hist.confidence < 7)
      return out;

   uint8_t probe_log2 = 5; /* 1/32 at confidence 4. */
   if (hist.confidence >= 7)
      probe_log2 = 7;      /* 1/128 */
   else if (hist.confidence >= 5)
      probe_log2 = 6;      /* 1/64 */

   const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
   const bool loser_probe = (decision_word & mask) == 0;

   out.override_mode = true;
   out.confidence = hist.confidence;
   out.probe_log2 = probe_log2;
   out.select_sysmem = prefer_sys ? !loser_probe : loser_probe;
   out.force_measure =
      loser_probe || (((decision_word >> 16) & 63u) == 0u);
   return out;
}

#endif
