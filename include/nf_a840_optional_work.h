/* SPDX-License-Identifier: MIT
 * NeuroFlow A840 noncritical GPU work admission gate.
 * Experimental, CPU-only policy; NOT connected to Mesa or hardware.
 *
 * This gate is for strictly optional telemetry/probes/learning jobs only.
 * NEVER use it to skip required GPU barriers, command dependencies,
 * required shader compilation, resource lifetime, or presentation.
 *
 * All methods are O(1), allocation-free, and have no sleeps, waits, locks,
 * syscalls or GPU calls. Single owner thread. Timestamps supplied by caller.
 * A timed-out dispatched job is NOT assumed to have completed: keep its GPU
 * resources owned by the original queue until a genuine completion/fault.
 */
#ifndef NF_A840_OPTIONAL_WORK_H
#define NF_A840_OPTIONAL_WORK_H

#include <stdbool.h>
#include <stdint.h>

struct nf_a840_optional_gate {
   uint64_t max_job_age_ns;
   uint64_t last_now_ns;
   uint64_t submitted_ns;
   uint64_t job_id;
   uint64_t skipped_busy;
   uint64_t skipped_budget;
   uint64_t timeouts;
   bool have_clock;
   bool pending;
   bool disabled;
};

static inline void
nf_a840_optional_init(struct nf_a840_optional_gate *g,
                      uint64_t max_job_age_ns)
{
   *g = (struct nf_a840_optional_gate) {
      .max_job_age_ns = max_job_age_ns ? max_job_age_ns : 1
   };
}

/* An asynchronous GPU job may complete after this check. A timeout cannot
 * cancel it and may NOT be used to reuse the fence, buffer, or command pool.
 * Disable custom optional work instead. Required rendering proceeds normally.
 */
static inline void
nf_a840_optional_check_age(struct nf_a840_optional_gate *g,
                           uint64_t now_ns)
{
   if (g->have_clock && now_ns < g->last_now_ns) {
      g->disabled = true;  /* broken monotonic clock input */
      return;
   }
   g->last_now_ns = now_ns;
   g->have_clock = true;
   if (g->pending && now_ns >= g->submitted_ns &&
       now_ns - g->submitted_ns > g->max_job_age_ns) {
      if (!g->disabled) ++g->timeouts;
      g->disabled = true;
      /* Leave pending=true: still owns potentially in-flight GPU resources. */
   }
}

/* Return true only when the OPTIONAL operation may be submitted. The caller
 * must have obtained an external per-pass budget without stalling. Failure
 * means SKIP, do not spin, enqueue, wait, or retry in the render hot path.
 */
static inline bool
nf_a840_optional_try_submit(struct nf_a840_optional_gate *g,
                            uint64_t now_ns,
                            uint64_t estimated_cost_ns,
                            uint64_t spare_budget_ns,
                            uint64_t *out_id)
{
   nf_a840_optional_check_age(g, now_ns);
   if (g->disabled) return false;
   if (g->pending) {
      ++g->skipped_busy;
      return false;
   }
   if (spare_budget_ns == 0 || estimated_cost_ns >= spare_budget_ns) {
      ++g->skipped_budget;
      return false;
   }
   g->pending = true;
   g->submitted_ns = now_ns;
   /* Reaching UINT64_MAX terminates optional work rather than reusing IDs. */
   if (g->job_id == UINT64_MAX) {
      g->disabled = true;
      g->pending = false;
      return false;
   }
   ++g->job_id;
   *out_id = g->job_id;
   return true;
}

/* Must be called ONLY after the actual job/fence is known to have completed,
 * not after a timeout or a speculative NPU estimate. Explicit fault latches
 * the optional path off; the host separately handles device-lost/recovery.
 */
static inline bool
nf_a840_optional_complete(struct nf_a840_optional_gate *g,
                           uint64_t job_id, bool correctness_ok)
{
   if (!g->pending || g->job_id != job_id)
      return false;
   g->pending = false;
   if (!correctness_ok)
      g->disabled = true;
   return true;
}

#endif /* NF_A840_OPTIONAL_WORK_H */
