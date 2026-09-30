/* SPDX-License-Identifier: MIT
 * Drnas Turnip V61 A810 SIGNATURE-GATED SCAN.
 *
 * V60 proved that recurrence is the right axis for limiting exploration, but
 * its cold target still forces 1+1 measurements on a rare pass. Those samples
 * cannot make V58 actionable because the learner needs six paired samples.
 *
 * V61 turns the scan into a completion/rescue mechanism:
 * - rare passes stay on Mesa PROFILED and learn naturally;
 * - structural pass cost selects how much recurrence is required before a
 *   forced probe is justified;
 * - existing natural measurements lower that threshold;
 * - once the learner is confidently ready, forced scanning stops;
 * - unresolved very-hot passes may receive a small extra evidence budget.
 *
 * Pure policy only: no GMEM layout, attachment programming, LRZ, barriers,
 * shaders, concurrent binning, WSI or Vulkan synchronization changes.
 */
#ifndef FRANE_MESA_26361_A810_SIGNATURE_SCAN_H
#define FRANE_MESA_26361_A810_SIGNATURE_SCAN_H

#include <cstdint>

#include "frane_mesa_26360_a810_frequency_scan.h"
#include "frane_mesa_26358_a810_tail_learner.h"

struct frane_26361_signature_info {
   uint16_t signature = 0;
   uint16_t start_occurrences = 128;
   uint8_t cost_class = 0; /* 0=moderate, 1=heavy, 2=very-heavy */
};

static inline uint8_t
frane_26361_bucket4(uint64_t v, uint64_t a, uint64_t b, uint64_t c)
{
   return v < a ? 0u : v < b ? 1u : v < c ? 2u : 3u;
}

static inline frane_26361_signature_info
frane_26361_signature_for(uint64_t replay_work,
                          uint64_t pass_pixels,
                          uint64_t estimated_tiles,
                          uint32_t drawcalls,
                          bool zs_load_store)
{
   frane_26361_signature_info out {};

   const uint8_t tile_bucket =
      frane_26361_bucket4(estimated_tiles, 6, 8, 12);
   const uint8_t replay_bucket =
      frane_26361_bucket4(replay_work, 192, 384, 768);
   const uint8_t draw_bucket =
      frane_26361_bucket4(drawcalls, 32, 64, 96);
   const uint8_t pixel_bucket =
      frane_26361_bucket4(pass_pixels,
                          1280ull * 720ull,
                          1920ull * 1080ull,
                          2560ull * 1440ull);

   out.signature =
      uint16_t(tile_bucket) |
      (uint16_t(replay_bucket) << 2) |
      (uint16_t(draw_bucket) << 4) |
      (uint16_t(pixel_bucket) << 6) |
      (zs_load_store ? uint16_t(1u << 8) : uint16_t(0));

   if (replay_work >= 768 ||
       estimated_tiles >= 12 ||
       pass_pixels >= 2560ull * 1440ull) {
      out.cost_class = 2;
      out.start_occurrences = 256;
   } else if (replay_work >= 384 ||
              estimated_tiles >= 8 ||
              drawcalls >= 96 ||
              pass_pixels >= 1920ull * 1080ull) {
      out.cost_class = 1;
      out.start_occurrences = 192;
   } else {
      out.cost_class = 0;
      out.start_occurrences = 128;
   }

   return out;
}

static inline uint32_t
frane_26361_sat_mul(uint32_t value, uint32_t mul)
{
   if (!mul || !value)
      return 0;
   if (value > UINT32_MAX / mul)
      return UINT32_MAX;
   return value * mul;
}

static inline frane_26359_scan_decision
frane_26361_decide_signature_scan(bool enabled,
                                  bool structural_tail_risk,
                                  frane_26359_scan_snapshot scan,
                                  uint32_t tail_learner_word,
                                  uint32_t occurrences,
                                  uint64_t replay_work,
                                  uint64_t pass_pixels,
                                  uint64_t estimated_tiles,
                                  uint32_t drawcalls,
                                  bool zs_load_store,
                                  uint32_t sysmem_probability,
                                  uint64_t decision_word)
{
   frane_26359_scan_decision out {};
   if (!enabled || !structural_tail_risk)
      return out;

   const auto learned =
      frane_26358_unpack_tail_snapshot(tail_learner_word);
   const auto sig =
      frane_26361_signature_for(replay_work, pass_pixels, estimated_tiles,
                                drawcalls, zs_load_store);

   const int confidence =
      learned.score < 0 ? -int(learned.score) : int(learned.score);

   /* Once V58 has enough evidence and a confident preference, exploration has
    * completed its job. This is the most important hard stop in V61.
    */
   if (learned.ready && confidence >= 4)
      return out;

   uint8_t target = 0;
   uint32_t activation = sig.start_occurrences;

   if (!learned.ready) {
      /* Do not pay for samples that cannot possibly make the learner useful.
       * Natural PROFILED samples reduce how long we wait before rescuing a
       * starved history.
       */
      if (learned.paired_samples >= 4)
         activation = sig.start_occurrences;
      else if (learned.paired_samples >= 2)
         activation = frane_26361_sat_mul(sig.start_occurrences, 2);
      else
         activation = frane_26361_sat_mul(sig.start_occurrences, 4);

      if (occurrences < activation)
         return out;

      target = 6; /* exact V58 readiness threshold */
   } else {
      /* Ready but inconclusive histories are allowed a little more evidence,
       * only if they are genuinely hot. Never keep scanning a merely warm RP.
       */
      const uint32_t hot8 =
         frane_26361_sat_mul(sig.start_occurrences, 8);
      const uint32_t hot16 =
         frane_26361_sat_mul(sig.start_occurrences, 16);

      if (occurrences >= hot16)
         target = 10;
      else if (occurrences >= hot8)
         target = 8;
      else
         return out;
   }

   const bool need_sys = scan.sysmem_samples < target;
   const bool need_gm = scan.gmem_samples < target;
   if (!need_sys && !need_gm)
      return out;

   bool choose_sys;
   if (need_sys && need_gm) {
      if (scan.sysmem_samples < scan.gmem_samples)
         choose_sys = true;
      else if (scan.gmem_samples < scan.sysmem_samples)
         choose_sys = false;
      else
         choose_sys = (occurrences & 1u) != 0u;
   } else {
      choose_sys = need_sys;
   }

   if (sysmem_probability > 100)
      sysmem_probability = 100;

   const bool hostile =
      (choose_sys && sysmem_probability <= 5) ||
      (!choose_sys && sysmem_probability >= 95);

   if (hostile) {
      /* Expensive signatures get fewer loser probes. As a pass proves it is
       * extremely hot, relax the throttle gradually so an actual regime
       * change can still be discovered.
       */
      uint8_t probe_log2 = uint8_t(4 + sig.cost_class); /* 1/16..1/64 */
      const uint32_t hot8 =
         frane_26361_sat_mul(sig.start_occurrences, 8);
      const uint32_t hot16 =
         frane_26361_sat_mul(sig.start_occurrences, 16);

      if (occurrences >= hot16 && probe_log2 > 2)
         probe_log2 = 2;
      else if (occurrences >= hot8 && probe_log2 > 3)
         probe_log2 = 3;

      if (probe_log2 > 6)
         probe_log2 = 6;

      const uint64_t mask = (UINT64_C(1) << probe_log2) - 1u;
      if (((decision_word >> 8) & mask) != 0u) {
         out.throttled = true;
         return out;
      }
   }

   out.override_mode = true;
   out.select_sysmem = choose_sys;
   out.force_measure = true;
   out.throttled = hostile;
   return out;
}

#endif
