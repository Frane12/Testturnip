/* SPDX-License-Identifier: MIT */
#include "nf_decision_debt.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>

static struct nf_debt_evidence
sample(bool comparable, bool safe, uint64_t baseline, uint64_t candidate,
       uint64_t eval, uint64_t transition, uint32_t pairs)
{
   return (struct nf_debt_evidence) {
      .baseline_ns = baseline, .candidate_ns = candidate,
      .decision_cpu_ns = eval, .transition_cpu_ns = transition,
      .paired_samples = pairs, .comparable = comparable,
      .correctness_ok = safe,
   };
}

static void
test_spacing(void)
{
   struct nf_debt_gate gate;
   struct nf_debt_config cfg = nf_debt_default_config();
   cfg.min_probe_spacing = 4;
   nf_debt_init(&gate, cfg);
   assert(nf_debt_should_probe(&gate));
   for (int i = 0; i < 3; ++i)
      assert(!nf_debt_should_probe(&gate));
   assert(nf_debt_should_probe(&gate));
}

static void
test_cooldown_and_recovery(void)
{
   struct nf_debt_gate gate;
   struct nf_debt_config cfg = nf_debt_default_config();
   cfg.min_probe_spacing = 2;
   cfg.max_probe_spacing = 8;
   cfg.cooldown_occurrences = 3;
   cfg.safety_margin_ns = 10;
   nf_debt_init(&gate, cfg);
   struct nf_debt_evidence lose = sample(false, true, 100, 10, 0, 0, 5);
   assert(nf_debt_record_window(&gate, &lose) == NF_DEBT_UNPROVEN);
   assert(nf_debt_record_window(&gate, &lose) == NF_DEBT_UNPROVEN);
   assert(gate.cooldowns == 1 && gate.spacing == 4);
   for (int i = 0; i < 3; ++i)
      assert(!nf_debt_should_probe(&gate));
   assert(nf_debt_should_probe(&gate));
   /* One win is insufficient to oscillate back to frequent evaluations. */
   struct nf_debt_evidence win = sample(true, true, 1000, 400, 30, 5, 3);
   assert(nf_debt_record_window(&gate, &win) == NF_DEBT_PROFITABLE);
   assert(gate.spacing == 4);
   assert(nf_debt_record_window(&gate, &win) == NF_DEBT_PROFITABLE);
   assert(nf_debt_record_window(&gate, &win) == NF_DEBT_PROFITABLE);
   assert(gate.spacing == 2);
   assert(gate.profitable_windows == 3);
}

static void
test_budget_and_overflow(void)
{
   struct nf_debt_config cfg = nf_debt_default_config();
   cfg.safety_margin_ns = 3;
   struct nf_debt_evidence ev = sample(true, true, 100, 90, 4, 3, 3);
   /* Net gain == margin is not enough to justify custom decisions. */
   assert(!nf_debt_is_profitable(&cfg, &ev));
   ev.candidate_ns = 89;
   assert(nf_debt_is_profitable(&cfg, &ev));
   ev = sample(true, true, UINT64_MAX, 0, UINT64_MAX, UINT64_MAX, 3);
   assert(!nf_debt_is_profitable(&cfg, &ev));
   ev = sample(true, true, UINT64_MAX, 0, 1, 1, 3);
   assert(nf_debt_is_profitable(&cfg, &ev));
   ev.paired_samples = 2;
   assert(!nf_debt_is_profitable(&cfg, &ev));
}

static void
test_safety_latch(void)
{
   struct nf_debt_gate gate;
   nf_debt_init(&gate, nf_debt_default_config());
   struct nf_debt_evidence bad = sample(true, false, 100, 1, 0, 0, 3);
   assert(nf_debt_should_probe(&gate));
   assert(nf_debt_record_window(&gate, &bad) == NF_DEBT_SAFETY_STOP);
   for (int i = 0; i < 100; ++i)
      assert(!nf_debt_should_probe(&gate));
   assert(nf_debt_record_window(&gate, &bad) == NF_DEBT_SAFETY_STOP);
   nf_debt_init(&gate, nf_debt_default_config());
   assert(nf_debt_should_probe(&gate));
}

static void
test_per_signature_independence(void)
{
   struct nf_debt_gate a, b;
   nf_debt_init(&a, nf_debt_default_config());
   nf_debt_init(&b, nf_debt_default_config());
   struct nf_debt_evidence lose = sample(false, true, 100, 1, 0, 0, 3);
   nf_debt_record_window(&a, &lose);
   nf_debt_record_window(&a, &lose);
   assert(a.cooldown_left > 0);
   assert(b.cooldown_left == 0);
   assert(nf_debt_should_probe(&b));
}

int
main(void)
{
   test_spacing();
   test_cooldown_and_recovery();
   test_budget_and_overflow();
   test_safety_latch();
   test_per_signature_independence();
   puts("NeuroFlow Decision Debt: all unit tests passed");
   return 0;
}
