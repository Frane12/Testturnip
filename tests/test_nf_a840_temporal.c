/* SPDX-License-Identifier: MIT */
#include "nf_a840_temporal.h"
#include <assert.h>
#include <limits.h>
#include <stdio.h>

static struct nf_a840_observation
obs(uint64_t t, uint64_t compat, uint32_t pattern, uint64_t cost)
{
   return (struct nf_a840_observation) {
      .timestamp_ns = t, .compatibility_key = compat,
      .pattern_key = pattern, .observed_cost_ns = cost,
      .cost_valid = true, .correctness_ok = true
   };
}

static void
three_events(struct nf_a840_controller *c)
{
   struct nf_a840_observation o = obs(100, 840, 1, 1000);
   assert(nf_a840_observe(c, &o));
   o = obs(200, 840, 1, 1000);
   assert(!nf_a840_observe(c, &o)); /* NO fixed-period sampling */
   o = obs(300, 840, 2, 1000);
   assert(nf_a840_observe(c, &o));
   o = obs(500, 840, 2, 1300);
   assert(nf_a840_observe(c, &o));
}

static struct nf_a840_prediction
prediction(const struct nf_a840_request *r, uint32_t N)
{
   return (struct nf_a840_prediction) {
      .request_id = r->request_id, .epoch = r->epoch,
      .event_seq = r->event_seq, .compatibility_key = r->compatibility_key,
      .proposed_N = N, .confidence_per_mille = 960,
      .expected_gain_ns = 100000
   };
}

static struct nf_a840_trial_evidence
win(void)
{
   return (struct nf_a840_trial_evidence) {
      .baseline_ns = 10000, .candidate_ns = 8000,
      .decision_cpu_ns = 100, .transition_cpu_ns = 100,
      .inference_amortized_ns = 100, .noise_margin_ns = 100,
      .baseline_p95_ns = 1200, .candidate_p95_ns = 1100,
      .paired_samples = 5, .comparable = true, .correctness_ok = true
   };
}

static void
test_event_driven_and_shadow(void)
{
   struct nf_a840_controller c;
   nf_a840_init(&c, nf_a840_default_config(), 840, 64);
   assert(c.mode == NF_A840_OBSERVER);
   assert(!nf_a840_set_mode(&c, NF_A840_SUPERVISED));
   struct nf_a840_observation foreign = obs(10, 810, 1, 100);
   assert(!nf_a840_observe(&c, &foreign));
   three_events(&c);
   struct nf_a840_request r;
   assert(nf_a840_take_request(&c, &r));
   assert(r.event_count == 3 && r.event_seq == 3);
   assert(r.events[0].dt_ns == 0);
   assert(r.events[1].dt_ns == 200);
   assert(r.events[2].dt_ns == 200);
   assert(!nf_a840_take_request(&c, &r));
   const struct nf_a840_prediction p = prediction(&r, 16);
   assert(nf_a840_offer_prediction(&c, &p, 600) == NF_A840_SHADOW_ONLY);
   assert(c.current_N == 64 && c.safe_N == 64);
   assert(c.shadows == 1);
   assert(!nf_a840_take_request(&c, &r)); /* no new event -> no inference */
}

static void
test_stale_prediction_rejected(void)
{
   struct nf_a840_controller c;
   nf_a840_init(&c, nf_a840_default_config(), 840, 64);
   three_events(&c);
   struct nf_a840_request r;
   assert(nf_a840_take_request(&c, &r));
   struct nf_a840_prediction p = prediction(&r, 16);
   struct nf_a840_observation o = obs(600, 840, 3, 1500);
   assert(nf_a840_observe(&c, &o)); /* event arrived during inference */
   assert(nf_a840_offer_prediction(&c, &p, 700) == NF_A840_REJECT);
   assert(c.current_N == 64 && !c.request_inflight);

   /* Restart to check out-of-order time and explicit expiry. */
   nf_a840_init(&c, nf_a840_default_config(), 840, 64);
   three_events(&c);
   assert(nf_a840_take_request(&c, &r));
   p = prediction(&r, 16);
   o = obs(100, 840, 4, 1400);
   assert(!nf_a840_observe(&c, &o));
   assert(nf_a840_offer_prediction(&c, &p,
              r.snapshot_ns + c.cfg.max_prediction_age_ns + 1)
          == NF_A840_REJECT);
   assert(c.current_N == 64);
}

static void
test_supervised_trial_and_fallback(void)
{
   struct nf_a840_controller c;
   struct nf_a840_config cfg = nf_a840_default_config();
   cfg.allow_supervised = true;
   nf_a840_init(&c, cfg, 840, 64);
   assert(c.mode == NF_A840_OBSERVER); /* opt-in still starts in SHADOW */
   assert(nf_a840_set_mode(&c, NF_A840_SUPERVISED));
   three_events(&c);
   struct nf_a840_request r;
   assert(nf_a840_take_request(&c, &r));
   struct nf_a840_prediction p = prediction(&r, 16);
   assert(nf_a840_offer_prediction(&c, &p, 600) == NF_A840_TRIAL);
   assert(c.current_N == 16 && c.safe_N == 64 && c.trial_active);
   struct nf_a840_trial_evidence e = win();
   assert(nf_a840_record_trial(&c, &e) == NF_A840_NO_CHANGE);
   assert(nf_a840_record_trial(&c, &e) == NF_A840_NO_CHANGE);
   assert(nf_a840_record_trial(&c, &e) == NF_A840_ACCEPT);
   assert(c.safe_N == 16 && !c.trial_active);

   /* Re-init: a single comparable p95 regression reverses the trial. */
   nf_a840_init(&c, cfg, 840, 64);
   assert(nf_a840_set_mode(&c, NF_A840_SUPERVISED));
   three_events(&c);
   assert(nf_a840_take_request(&c, &r));
   p = prediction(&r, 8);
   assert(nf_a840_offer_prediction(&c, &p, 600) == NF_A840_TRIAL);
   e = win();
   e.candidate_p95_ns = 1300;
   assert(nf_a840_record_trial(&c, &e) == NF_A840_FALLBACK);
   assert(c.current_N == 64 && c.safe_N == 64 && !c.trial_active);

   /* Re-init: inconclusive A/B cannot leave a trial running indefinitely. */
   nf_a840_init(&c, cfg, 840, 64);
   assert(nf_a840_set_mode(&c, NF_A840_SUPERVISED));
   three_events(&c);
   assert(nf_a840_take_request(&c, &r));
   p = prediction(&r, 8);
   assert(nf_a840_offer_prediction(&c, &p, 600) == NF_A840_TRIAL);
   e = win();
   e.comparable = false;
   assert(nf_a840_record_trial(&c, &e) == NF_A840_NO_CHANGE);
   assert(nf_a840_record_trial(&c, &e) == NF_A840_FALLBACK);
   assert(c.current_N == 64);
}

static void
test_safety_and_overflow(void)
{
   struct nf_a840_controller c;
   struct nf_a840_config cfg = nf_a840_default_config();
   cfg.allow_supervised = true;
   nf_a840_init(&c, cfg, 840, 64);
   assert(nf_a840_set_mode(&c, NF_A840_SUPERVISED));
   three_events(&c);
   struct nf_a840_request r;
   assert(nf_a840_take_request(&c, &r));
   struct nf_a840_prediction p = prediction(&r, 4);
   assert(nf_a840_offer_prediction(&c, &p, 600) == NF_A840_TRIAL);
   struct nf_a840_observation bad = obs(601, 840, 4, 2000);
   bad.correctness_ok = false;
   assert(!nf_a840_observe(&c, &bad));
   assert(c.safety_blocked && c.current_N == 64);
   assert(!nf_a840_set_mode(&c, NF_A840_SUPERVISED));
   assert(nf_a840_offer_prediction(&c, &p, 602) == NF_A840_REJECT);

   struct nf_a840_trial_evidence e = win();
   e.baseline_ns = UINT64_MAX;
   e.candidate_ns = 0;
   e.decision_cpu_ns = UINT64_MAX;
   assert(!nf_a840_profitable(&e));
   e.decision_cpu_ns = 1;
   assert(nf_a840_profitable(&e));
   e.comparable = false;
   assert(!nf_a840_profitable(&e));
}

static void
test_ring_order_and_bounds(void)
{
   struct nf_a840_controller c;
   nf_a840_init(&c, nf_a840_default_config(), 840, 64);
   for (uint32_t i = 1; i <= 20; ++i) {
      struct nf_a840_observation o = obs(i * 100, 840, i, 1000);
      assert(nf_a840_observe(&c, &o));
   }
   struct nf_a840_request r;
   assert(nf_a840_take_request(&c, &r));
   assert(r.event_count == NF_A840_EVENT_CAP);
   assert(r.events[0].pattern_key == 9);
   assert(r.events[11].pattern_key == 20);
   struct nf_a840_prediction p = prediction(&r, 0); /* illegal N */
   assert(nf_a840_offer_prediction(&c, &p, 2100) == NF_A840_REJECT);
   assert(c.current_N == 64);
}

static void
test_slow_drift_and_invalid_baseline(void)
{
   struct nf_a840_controller c;
   nf_a840_init(&c, nf_a840_default_config(), 840, 64);
   struct nf_a840_observation o = obs(100, 840, 1, 1000);
   assert(nf_a840_observe(&c, &o));
   o = obs(200, 840, 1, 1100);
   assert(!nf_a840_observe(&c, &o));
   o = obs(300, 840, 1, 1200);
   assert(nf_a840_observe(&c, &o)); /* accumulates from 1000 anchor */
   assert(c.event_count == 2);
   assert(c.events[1].dt_ns == 200);

   nf_a840_init(&c, nf_a840_default_config(), 840, 5000);
   assert(c.safety_blocked); /* unverified N must not be auto-installed */
   o = obs(400, 840, 1, 1000);
   assert(!nf_a840_observe(&c, &o));
}

static void
test_inference_backpressure(void)
{
   struct nf_a840_controller c;
   nf_a840_init(&c, nf_a840_default_config(), 840, 64);
   three_events(&c);
   struct nf_a840_request r;
   assert(nf_a840_take_request(&c, &r));
   struct nf_a840_prediction p = prediction(&r, 32);
   assert(nf_a840_offer_prediction(&c, &p, 600) == NF_A840_SHADOW_ONLY);
   for (uint32_t i = 3; i < 7; ++i) {
      struct nf_a840_observation o = obs(600 + i * 100, 840, i, 1500);
      assert(nf_a840_observe(&c, &o));
   }
   /* Enough events, but insufficient elapsed time: avoid NPU overload. */
   assert(!nf_a840_take_request(&c, &r));
   struct nf_a840_observation o =
      obs(UINT64_C(250001000), 840, 10, 1600);
   assert(nf_a840_observe(&c, &o));
   assert(nf_a840_take_request(&c, &r));
   assert(r.event_seq == c.event_seq);
}

int main(void)
{
   test_event_driven_and_shadow();
   test_stale_prediction_rejected();
   test_supervised_trial_and_fallback();
   test_safety_and_overflow();
   test_ring_order_and_bounds();
   test_slow_drift_and_invalid_baseline();
   test_inference_backpressure();
   puts("NeuroFlow A840 temporal observer: all tests passed");
   return 0;
}
