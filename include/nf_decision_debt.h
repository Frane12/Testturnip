/*
 * NeuroFlow Decision Debt — bounded, evidence-gated tuning policy.
 * Copyright (c) 2026 Drnas Turnip contributors.
 * SPDX-License-Identifier: MIT
 *
 * Reference module only. The Mesa Turnip render path is NOT modified here.
 * Instantiate one gate per comparable, recurring render-pass signature.
 * There are no locks, allocations, clocks or driver dependencies.
 */
#ifndef NF_DECISION_DEBT_H
#define NF_DECISION_DEBT_H

#include <stdbool.h>
#include <stdint.h>

enum nf_debt_result {
   NF_DEBT_PROFITABLE,
   NF_DEBT_UNPROVEN,
   NF_DEBT_SAFETY_STOP,
};

struct nf_debt_config {
   uint32_t min_probe_spacing;   /* render-pass occurrences */
   uint32_t max_probe_spacing;
   uint32_t cooldown_occurrences;
   uint32_t min_paired_samples;
   uint8_t losses_before_cooldown;
   uint8_t wins_before_acceleration;
   uint64_t safety_margin_ns;    /* per evidence window, not per frame */
};

struct nf_debt_evidence {
   /* Comparable A/B totals for the SAME workload and measurement window.
    * Time excluding tuning CPU overhead; measure overhead separately.
    * Values are wall-clock latency estimates, NOT raw GPU timestamps.
    */
   uint64_t baseline_ns;
   uint64_t candidate_ns;
   uint64_t decision_cpu_ns;
   uint64_t transition_cpu_ns;
   uint32_t paired_samples;
   bool comparable;
   bool correctness_ok;
};

struct nf_debt_gate {
   struct nf_debt_config cfg;
   uint32_t spacing;
   uint32_t until_probe;
   uint32_t cooldown_left;
   uint8_t consecutive_losses;
   uint8_t consecutive_wins;
   bool safety_blocked;
   /* Updated only after probes; read off the hot path. */
   uint64_t profitable_windows;
   uint64_t unproven_windows;
   uint64_t cooldowns;
};

static inline struct nf_debt_config
nf_debt_default_config(void)
{
   return (struct nf_debt_config) {
      .min_probe_spacing = 64,
      .max_probe_spacing = 1024,
      .cooldown_occurrences = 256,
      .min_paired_samples = 3,
      .losses_before_cooldown = 2,
      .wins_before_acceleration = 3,
      .safety_margin_ns = 0, /* integrator supplies A/B noise floor */
   };
}

static inline void
nf_debt_init(struct nf_debt_gate *gate, struct nf_debt_config cfg)
{
   if (cfg.min_probe_spacing == 0)
      cfg.min_probe_spacing = 1;
   if (cfg.max_probe_spacing < cfg.min_probe_spacing)
      cfg.max_probe_spacing = cfg.min_probe_spacing;
   if (cfg.min_paired_samples == 0)
      cfg.min_paired_samples = 1;
   if (cfg.losses_before_cooldown == 0)
      cfg.losses_before_cooldown = 1;
   if (cfg.wins_before_acceleration == 0)
      cfg.wins_before_acceleration = 1;
   *gate = (struct nf_debt_gate) { .cfg = cfg, .spacing = cfg.min_probe_spacing };
}

/* Constant-time, cheap gate. False means reuse existing safe Mesa decision.
 * Only call for the SAME recurring render-pass signature. This function does
 * not choose GMEM/SYSMEM, and never bypasses correctness or Mesa PROFILED.
 */
static inline bool
nf_debt_should_probe(struct nf_debt_gate *gate)
{
   if (gate->safety_blocked)
      return false;
   if (gate->cooldown_left) {
      --gate->cooldown_left;
      return false;
   }
   if (gate->until_probe) {
      --gate->until_probe;
      return false;
   }
   gate->until_probe = gate->spacing - 1;
   return true;
}

/* Overflow-safe comparison: gain must EXCEED total estimated overhead and
 * confidence margin. Untrusted / cold evidence does not certify a gain.
 */
static inline bool
nf_debt_is_profitable(const struct nf_debt_config *cfg,
                      const struct nf_debt_evidence *ev)
{
   if (!ev->comparable || ev->paired_samples < cfg->min_paired_samples ||
       ev->baseline_ns <= ev->candidate_ns)
      return false;

   uint64_t remaining = ev->baseline_ns - ev->candidate_ns;
   if (remaining <= ev->decision_cpu_ns)
      return false;
   remaining -= ev->decision_cpu_ns;
   if (remaining <= ev->transition_cpu_ns)
      return false;
   remaining -= ev->transition_cpu_ns;
   return remaining > cfg->safety_margin_ns;
}

/* Call once after a completed evaluation window, not every frame. Safety
 * failure latches off CUSTOM probing until an explicit init/reset. This gate
 * never changes the actual renderer: the caller must select a safe fallback.
 */
static inline enum nf_debt_result
nf_debt_record_window(struct nf_debt_gate *gate,
                      const struct nf_debt_evidence *ev)
{
   if (gate->safety_blocked)
      return NF_DEBT_SAFETY_STOP;
   if (!ev->correctness_ok) {
      gate->safety_blocked = true;
      gate->consecutive_losses = 0;
      gate->consecutive_wins = 0;
      return NF_DEBT_SAFETY_STOP;
   }

   if (nf_debt_is_profitable(&gate->cfg, ev)) {
      ++gate->profitable_windows;
      gate->consecutive_losses = 0;
      ++gate->consecutive_wins;
      if (gate->consecutive_wins >= gate->cfg.wins_before_acceleration) {
         uint32_t half = gate->spacing / 2;
         gate->spacing = half > gate->cfg.min_probe_spacing
                            ? half : gate->cfg.min_probe_spacing;
         gate->consecutive_wins = 0;
      }
      return NF_DEBT_PROFITABLE;
   }

   ++gate->unproven_windows;
   gate->consecutive_wins = 0;
   ++gate->consecutive_losses;
   if (gate->consecutive_losses >= gate->cfg.losses_before_cooldown) {
      gate->consecutive_losses = 0;
      /* Avoid uint32 overflow when doubling. */
      gate->spacing = gate->spacing >= gate->cfg.max_probe_spacing / 2
                       ? gate->cfg.max_probe_spacing : gate->spacing * 2;
      gate->cooldown_left = gate->cfg.cooldown_occurrences;
      ++gate->cooldowns;
   }
   return NF_DEBT_UNPROVEN;
}

#endif /* NF_DECISION_DEBT_H */
