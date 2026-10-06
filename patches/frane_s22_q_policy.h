/* SPDX-License-Identifier: MIT
 * S2.3 Q2 conservative clean-room renderpass policy.
 *
 * No proprietary Qualcomm code. This is an independent bounded prior from
 * observable workload classes. It must never bypass Turnip LRZ correctness.
 */
#ifndef FRANE_S22_Q_POLICY_H
#define FRANE_S22_Q_POLICY_H

#include <algorithm>
#include <cstdint>

struct frane_s22_q_rp_input {
   uint32_t draw_count = 0;
   uint32_t indirect_draw_count = 0;
   uint32_t depth_test_draw_count = 0;
   uint32_t depth_write_draw_count = 0;
   uint32_t stencil_draw_count = 0;
   uint32_t stencil_write_draw_count = 0;
   uint32_t lrz_candidate_draw_count = 0;
   uint32_t lrz_late_draw_count = 0;
   uint32_t stencil_last_draw = 0;
   uint32_t lrz_disabled_at_draw_plus1 = 0;
   uint32_t lrz_write_disabled_at_draw_plus1 = 0;
   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
};

struct frane_s22_q_rp_eval {
   bool valid = false;
   int8_t score_delta = 0; /* S2.3 Q2 hard bound: -4..+4 */
};

static inline bool
frane_s22_q_ratio_le(uint64_t lhs, uint64_t rhs, uint32_t num, uint32_t den)
{
   if (!rhs || !den)
      return false;
   return lhs * uint64_t(den) <= rhs * uint64_t(num);
}

static inline frane_s22_q_rp_eval
frane_s22_q_eval(const frane_s22_q_rp_input &in)
{
   frane_s22_q_rp_eval out {};
   if (!in.draw_count)
      return out;

   out.valid = true;
   int delta = 0;

   const uint64_t sys = in.sysmem_bandwidth_per_pixel;
   const uint64_t gm = in.gmem_bandwidth_per_pixel;
   const bool have_traffic = sys && gm;
   const bool bw_good =
      have_traffic && frane_s22_q_ratio_le(gm, sys, 7, 8);
   const bool bw_very_good =
      have_traffic && frane_s22_q_ratio_le(gm, sys, 2, 3);
   const bool bw_bad =
      have_traffic && frane_s22_q_ratio_le(sys, gm, 8, 9);

   const bool draw_dense = in.draw_count >= 32;
   const bool draw_very_dense = in.draw_count >= 96;

   bool lrz_good = false;
   bool lrz_bad = false;
   if (in.lrz_candidate_draw_count >= 8) {
      lrz_good =
         uint64_t(in.lrz_late_draw_count) * 4 <=
         in.lrz_candidate_draw_count;
      lrz_bad =
         uint64_t(in.lrz_late_draw_count) * 2 >=
         in.lrz_candidate_draw_count;
   }

   bool early_lrz_disable = false;
   if (in.lrz_disabled_at_draw_plus1) {
      const uint32_t at = in.lrz_disabled_at_draw_plus1 - 1;
      early_lrz_disable = uint64_t(at) * 4 <= in.draw_count;
   }
   bool early_lrz_write_disable = false;
   if (in.lrz_write_disabled_at_draw_plus1) {
      const uint32_t at = in.lrz_write_disabled_at_draw_plus1 - 1;
      early_lrz_write_disable = uint64_t(at) * 4 <= in.draw_count;
   }

   /*
    * Positive Q2 bias is intentionally strict: bandwidth, draw density and
    * LRZ quality must all agree. This prevents one attractive signal from
    * steering an otherwise ambiguous renderpass.
    */
   if (bw_good && draw_dense && lrz_good &&
       !early_lrz_disable && !early_lrz_write_disable) {
      delta += 2;
      if (bw_very_good && draw_very_dense)
         delta += 1;
      if (in.indirect_draw_count >= 2 &&
          uint64_t(in.indirect_draw_count) * 4 >= in.draw_count)
         delta += 1;
   }

   /* Negative evidence stays useful, but is also tightly bounded. */
   if (in.draw_count <= 6 && !bw_good)
      delta -= 2;
   if (bw_bad)
      delta -= 1;
   if (lrz_bad)
      delta -= 2;
   if (early_lrz_disable)
      delta -= 2;
   if (early_lrz_write_disable)
      delta -= 1;

   if (in.stencil_draw_count && in.stencil_last_draw &&
       uint64_t(in.stencil_last_draw) * 4 >=
          uint64_t(in.draw_count) * 3)
      delta -= 1;

   out.score_delta = int8_t(std::clamp(delta, -4, 4));
   return out;
}

#endif
