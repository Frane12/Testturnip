/* SPDX-License-Identifier: MIT
 * S2.2 Q-LRZ clean-room renderpass policy.
 *
 * This helper contains no Qualcomm code.  It is an independent, bounded
 * policy derived from public/observable workload categories: draw density,
 * indirect-command density, attachment traffic, and LRZ/stencil behaviour.
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

   /* +1 encoding: zero means "not disabled", one means disabled before draw 0. */
   uint32_t lrz_disabled_at_draw_plus1 = 0;
   uint32_t lrz_write_disabled_at_draw_plus1 = 0;

   uint32_t sysmem_bandwidth_per_pixel = 0;
   uint32_t gmem_bandwidth_per_pixel = 0;
};

struct frane_s22_q_rp_eval {
   bool valid = false;
   int8_t score_delta = 0; /* deliberately bounded: -12..+10 */
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
   const bool gmem_clear_win =
      have_traffic && frane_s22_q_ratio_le(gm, sys, 7, 8);
   const bool gmem_clear_loss =
      have_traffic && frane_s22_q_ratio_le(sys, gm, 8, 9);

   /*
    * A small RP rarely amortizes tile/bin replay unless attachment traffic
    * clearly favours GMEM.  Conversely, dense RPs get a small extra prior
    * only when Mesa's own load/store estimate agrees.
    */
   if (in.draw_count <= 6 && !gmem_clear_win)
      delta -= 4;
   else if (in.draw_count >= 32 && gmem_clear_win)
      delta += 3;

   if (in.draw_count >= 96 && gmem_clear_win)
      delta += 2;

   /*
    * Indirect-heavy work often represents many GPU-generated/CPU-cheap draws.
    * Treat it as a secondary signal, never as a force-mode decision.
    */
   if (in.indirect_draw_count >= 2 &&
       uint64_t(in.indirect_draw_count) * 4 >= in.draw_count) {
      if (gmem_clear_win)
         delta += 2;
      else if (gmem_clear_loss)
         delta -= 2;
   }

   /*
    * LRZ quality signal.  We never enable LRZ or weaken correctness rules;
    * this only says whether an RP is likely to retain useful early-Z work.
    */
   if (in.lrz_candidate_draw_count >= 8) {
      if (uint64_t(in.lrz_late_draw_count) * 4 <=
          in.lrz_candidate_draw_count)
         delta += 2;
      else if (uint64_t(in.lrz_late_draw_count) * 2 >=
               in.lrz_candidate_draw_count)
         delta -= 3;
   }

   /* An early persistent LRZ disable is evidence against an aggressive prior. */
   if (in.lrz_disabled_at_draw_plus1) {
      const uint32_t at = in.lrz_disabled_at_draw_plus1 - 1;
      if (uint64_t(at) * 4 <= in.draw_count)
         delta -= 3;
   }
   if (in.lrz_write_disabled_at_draw_plus1) {
      const uint32_t at = in.lrz_write_disabled_at_draw_plus1 - 1;
      if (uint64_t(at) * 4 <= in.draw_count)
         delta -= 2;
   }

   /*
    * Late stencil use can reduce the value of optimistic early-Z/bin reuse.
    * Keep the penalty tiny because Turnip's actual LRZ state machine remains
    * the correctness authority.
    */
   if (in.stencil_draw_count && in.stencil_last_draw &&
       uint64_t(in.stencil_last_draw) * 4 >=
          uint64_t(in.draw_count) * 3)
      delta -= 1;

   out.score_delta =
      int8_t(std::clamp(delta, -12, 10));
   return out;
}

#endif
