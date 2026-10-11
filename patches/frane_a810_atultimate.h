/* SPDX-License-Identifier: MIT
 * ATUltimate A810: bounded history-aware protection on top of AT8.
 * Source of truth: existing AT3 associative GPU-timestamp history.
 * This policy NEVER picks a fixed GMEM/SYSMEM mode: it only rejects an
 * AT6 heuristic when fresh, paired GPU evidence directly contradicts it.
 */
#ifndef FRANE_A810_ATULTIMATE_H
#define FRANE_A810_ATULTIMATE_H
#include "frane_a810_at8_early.h"

static inline bool
frane_atu_history_confident(const frane_s1at1_context_input &in,
                            const frane_s1at3_snapshot &s)
{
   const auto c = frane_s1at1_catalog_for(in);
   const unsigned pairs = std::min(s.samples[0], s.samples[1]);
   return c.signature && c.signature == s.signature &&
      pairs >= 2 && std::abs(int(s.score)) >= 8 &&
      s.at7_saving_4us >= 40 /* >=160 us conservative GPU bound */ &&
      s.at7_noise_q8 <= 80 && s.volatility <= 3 &&
      !s.stale[0] && !s.stale[1];
}

static inline frane_s1at1_decision
frane_atu_protect_prior(const frane_s1at1_context_input &in,
                        const frane_s1at3_snapshot &s,
                        const frane_s1at1_decision &at4,
                        const frane_s1at1_decision &prior,
                        bool *rejected = nullptr)
{
   /* Never interfere with existing AT4 decisions, paired probes, or a
    * reasonable probabilistic prior. No hard switch to the winner.
    * This is the opposite of the FC2 AT9 regression's forced choices.
    */
   if (!prior.override_mode || at4.override_mode || at4.force_measure ||
       !frane_atu_history_confident(in, s))
      return prior;
   const bool measured_sysmem_faster = s.score < 0;
   const bool prior_forces_against_evidence =
      (measured_sysmem_faster && prior.effective_sysmem_probability < 38) ||
      (!measured_sysmem_faster && prior.effective_sysmem_probability > 62);
   if (!prior_forces_against_evidence)
      return prior;
   if (rejected)
      *rejected = true;
   return {}; /* Fall back to existing selector rather than force a mode. */
}
#endif
