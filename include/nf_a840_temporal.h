/* SPDX-License-Identifier: MIT
 * NeuroFlow A840 Temporal Observer v0.1 — CPU safety gate / NPU-ready contract.
 * REFERENCE ONLY: no Mesa render-path hook, no QNN/HTP implementation.
 * One instance per *compatible* render-pass class, owned by one CPU thread.
 * NPU worker receives COPIES of requests; it must never mutate this state.
 */
#ifndef NF_A840_TEMPORAL_H
#define NF_A840_TEMPORAL_H
#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#define NF_A840_EVENT_CAP 12u
#define NF_A840_DEFAULT_MAX_AGE_NS UINT64_C(1000000000)

enum nf_a840_mode { NF_A840_OBSERVER = 0, NF_A840_SUPERVISED = 1 };
enum nf_a840_result {
   NF_A840_NO_CHANGE, NF_A840_SHADOW_ONLY, NF_A840_TRIAL,
   NF_A840_ACCEPT, NF_A840_FALLBACK, NF_A840_REJECT
};

struct nf_a840_config {
   uint32_t min_N, max_N;
   uint16_t change_threshold_per_mille;
   uint16_t min_events_for_inference;
   uint16_t min_confidence_per_mille;
   uint8_t wins_to_accept, unknowns_to_fallback;
   uint64_t max_prediction_age_ns;
   bool allow_supervised; /* DEFAULT FALSE; explicit integrator opt-in only */
};

/* Caller supplies data that was ALREADY available at a completed legal
 * observation boundary. No new GPU queries, allocation, or timer reads here.
 * compatibility_key is a correctness/synchronization domain, NOT game ID.
 * pattern_key describes a changing workload pattern, NOT a safety waiver.
 */
struct nf_a840_observation {
   uint64_t timestamp_ns; /* monotonic */
   uint64_t compatibility_key;
   uint32_t pattern_key;
   uint64_t observed_cost_ns;
   bool cost_valid;
   bool correctness_ok;
};

struct nf_a840_event {
   uint64_t dt_ns; /* elapsed time between significant observations */
   uint32_t pattern_key;
   uint64_t observed_cost_ns;
   bool cost_valid;
};

/* Immutable snapshot. Copy/queue off the render path for a future QNN/HTP
 * adapter. NPU inference is NOT implemented in this module.
 */
struct nf_a840_request {
   uint64_t request_id, epoch, event_seq, compatibility_key;
   uint64_t snapshot_ns;
   uint32_t current_N, safe_N;
   uint8_t event_count;
   struct nf_a840_event events[NF_A840_EVENT_CAP];
};

struct nf_a840_prediction {
   uint64_t request_id, epoch, event_seq, compatibility_key;
   uint32_t proposed_N;
   uint16_t confidence_per_mille; /* MUST be calibrated before trusting */
   uint64_t expected_gain_ns; /* informational, NEVER sufficient evidence */
};

/* Compare completed equivalent A/B windows with real measurements.
 * The estimates cannot capture all CPU/GPU overlap; validate full-stack
 * frame time separately. Unsafe render paths must be filtered by Mesa.
 */
struct nf_a840_trial_evidence {
   uint64_t baseline_ns, candidate_ns;
   uint64_t decision_cpu_ns, transition_cpu_ns, inference_amortized_ns;
   uint64_t noise_margin_ns;
   uint64_t baseline_p95_ns, candidate_p95_ns;
   uint32_t paired_samples;
   bool comparable, correctness_ok;
};

struct nf_a840_controller {
   struct nf_a840_config cfg;
   enum nf_a840_mode mode;
   uint64_t compatibility_key, epoch, event_seq, next_request_id;
   uint64_t last_timestamp_ns, last_event_ns;
   uint32_t last_pattern_key, current_N, safe_N;
   uint64_t last_cost_ns;
   bool have_last, last_cost_valid, safety_blocked;
   struct nf_a840_event events[NF_A840_EVENT_CAP];
   uint8_t event_count, event_next;
   uint16_t events_since_request;
   bool request_inflight, trial_active;
   uint64_t inflight_request_id, inflight_event_seq, inflight_epoch;
   uint64_t inflight_snapshot_ns;
   uint8_t trial_wins, trial_unknowns;
   uint64_t shadows, stale_rejections, fallbacks;
};

static inline struct nf_a840_config
nf_a840_default_config(void)
{
   return (struct nf_a840_config) {
      .min_N = 1, .max_N = 1024,
      .change_threshold_per_mille = 150, /* candidate; measure on device */
      .min_events_for_inference = 3,
      .min_confidence_per_mille = 900, /* not a calibrated probability */
      .wins_to_accept = 3, .unknowns_to_fallback = 2,
      .max_prediction_age_ns = NF_A840_DEFAULT_MAX_AGE_NS,
      .allow_supervised = false
   };
}

static inline void
nf_a840_init(struct nf_a840_controller *c, struct nf_a840_config cfg,
             uint64_t compatibility_key, uint32_t verified_safe_N)
{
   if (!cfg.min_N) cfg.min_N = 1;
   if (cfg.max_N < cfg.min_N) cfg.max_N = cfg.min_N;
   if (!cfg.min_events_for_inference) cfg.min_events_for_inference = 1;
   if (cfg.min_events_for_inference > NF_A840_EVENT_CAP)
      cfg.min_events_for_inference = NF_A840_EVENT_CAP;
   if (!cfg.wins_to_accept) cfg.wins_to_accept = 1;
   if (!cfg.unknowns_to_fallback) cfg.unknowns_to_fallback = 1;
   if (!cfg.max_prediction_age_ns) cfg.max_prediction_age_ns = 1;
   if (cfg.min_confidence_per_mille > 1000)
      cfg.min_confidence_per_mille = 1000;
   if (cfg.change_threshold_per_mille > 1000)
      cfg.change_threshold_per_mille = 1000;
   memset(c, 0, sizeof(*c));
   c->cfg = cfg;
   c->mode = NF_A840_OBSERVER; /* even if opt-in capability is configured */
   c->compatibility_key = compatibility_key;
   c->safe_N = verified_safe_N >= cfg.min_N && verified_safe_N <= cfg.max_N
                   ? verified_safe_N : cfg.max_N;
   c->current_N = c->safe_N;
   c->epoch = 1;
}

static inline bool
nf_a840_set_mode(struct nf_a840_controller *c, enum nf_a840_mode mode)
{
   if (mode != NF_A840_OBSERVER && mode != NF_A840_SUPERVISED)
      return false;
   if (mode == NF_A840_SUPERVISED &&
       (!c->cfg.allow_supervised || c->safety_blocked))
      return false;
   if (mode == NF_A840_OBSERVER && c->trial_active) {
      c->current_N = c->safe_N;
      c->trial_active = false;
      ++c->fallbacks;
   }
   c->mode = mode;
   return true;
}

/* Safety/correctness failure: immediately stop experimentation. No NPU
 * result may bypass the latch. Actual Mesa fallback is caller's obligation.
 */
static inline enum nf_a840_result
nf_a840_safety_stop(struct nf_a840_controller *c)
{
   c->safety_blocked = true;
   c->current_N = c->safe_N;
   c->trial_active = false;
   c->request_inflight = false;
   ++c->fallbacks;
   return NF_A840_FALLBACK;
}

static inline bool
nf_a840_significant_cost_change(uint64_t prev, uint64_t current,
                                uint16_t threshold_per_mille)
{
   if (prev == 0) return current != 0;
   uint64_t delta = prev > current ? prev - current : current - prev;
   /* Avoid delta*1000 overflow and accept near-threshold conservatively. */
   return delta >= prev / 1000 * threshold_per_mille +
           (prev % 1000 * threshold_per_mille + 999) / 1000;
}

/* CALL ONLY WHEN EXISTING TELEMETRY HAS ARRIVED, not on a timer.
 * Record only meaningful change events; zero extra driver/GPU queries.
 * Foreign compatibility domains and out-of-order timestamps are rejected.
 */
static inline bool
nf_a840_observe(struct nf_a840_controller *c,
                const struct nf_a840_observation *o)
{
   if (c->safety_blocked || o->compatibility_key != c->compatibility_key)
      return false;
   if (!o->correctness_ok) {
      nf_a840_safety_stop(c);
      return false;
   }
   if (c->have_last && o->timestamp_ns <= c->last_timestamp_ns)
      return false;
   bool important = !c->have_last || o->pattern_key != c->last_pattern_key;
   if (!important && o->cost_valid && c->last_cost_valid)
      important = nf_a840_significant_cost_change(
         c->last_cost_ns, o->observed_cost_ns,
         c->cfg.change_threshold_per_mille);
   if (important) {
      struct nf_a840_event *e = &c->events[c->event_next];
      *e = (struct nf_a840_event) {
         .dt_ns = c->event_seq ? o->timestamp_ns - c->last_event_ns : 0,
         .pattern_key = o->pattern_key,
         .observed_cost_ns = o->observed_cost_ns,
         .cost_valid = o->cost_valid
      };
      c->event_next = (uint8_t)((c->event_next + 1) % NF_A840_EVENT_CAP);
      if (c->event_count < NF_A840_EVENT_CAP) ++c->event_count;
      if (c->events_since_request < UINT16_MAX) ++c->events_since_request;
      c->last_event_ns = o->timestamp_ns;
      ++c->event_seq;
   }
   c->last_timestamp_ns = o->timestamp_ns;
   c->last_pattern_key = o->pattern_key;
   c->last_cost_ns = o->observed_cost_ns;
   c->last_cost_valid = o->cost_valid;
   c->have_last = true;
   return important;
}

/* CPU owner builds a snapshot; NPU worker receives only this immutable copy.
 * This function does NOT call NPU and does NOT block GPU.
 */
static inline bool
nf_a840_take_request(struct nf_a840_controller *c,
                     struct nf_a840_request *r)
{
   if (c->safety_blocked || c->request_inflight || c->trial_active ||
       c->event_count < c->cfg.min_events_for_inference ||
       c->events_since_request < c->cfg.min_events_for_inference)
      return false;
   memset(r, 0, sizeof(*r));
   r->request_id = ++c->next_request_id;
   r->epoch = c->epoch;
   r->event_seq = c->event_seq;
   r->compatibility_key = c->compatibility_key;
   r->snapshot_ns = c->last_event_ns;
   r->current_N = c->current_N;
   r->safe_N = c->safe_N;
   r->event_count = c->event_count;
   const uint8_t oldest = (uint8_t)((c->event_next +
                             NF_A840_EVENT_CAP - c->event_count)
                             % NF_A840_EVENT_CAP);
   for (uint8_t i = 0; i < c->event_count; ++i)
      r->events[i] = c->events[(oldest + i) % NF_A840_EVENT_CAP];
   c->request_inflight = true;
   c->inflight_request_id = r->request_id;
   c->inflight_event_seq = r->event_seq;
   c->inflight_epoch = r->epoch;
   c->inflight_snapshot_ns = r->snapshot_ns;
   c->events_since_request = 0;
   return true;
}

static inline enum nf_a840_result
nf_a840_offer_prediction(struct nf_a840_controller *c,
                          const struct nf_a840_prediction *p,
                          uint64_t now_ns)
{
   if (!c->request_inflight || p->request_id != c->inflight_request_id)
      return NF_A840_REJECT;
   c->request_inflight = false;
   if (c->safety_blocked || p->epoch != c->inflight_epoch ||
       p->epoch != c->epoch ||
       p->event_seq != c->inflight_event_seq ||
       p->event_seq != c->event_seq ||
       p->compatibility_key != c->compatibility_key ||
       now_ns < c->inflight_snapshot_ns ||
       now_ns - c->inflight_snapshot_ns > c->cfg.max_prediction_age_ns ||
       p->proposed_N < c->cfg.min_N || p->proposed_N > c->cfg.max_N ||
       p->confidence_per_mille < c->cfg.min_confidence_per_mille ||
       p->confidence_per_mille > 1000) {
      ++c->stale_rejections;
      return NF_A840_REJECT;
   }
   if (c->mode != NF_A840_SUPERVISED || !c->cfg.allow_supervised) {
      ++c->shadows;
      return NF_A840_SHADOW_ONLY;
   }
   if (c->trial_active || p->proposed_N == c->current_N)
      return NF_A840_NO_CHANGE;
   /* PROVISIONAL schedule only: caller still enforces legal pass boundary,
    * Mesa correctness and synchronization. No GPU mode is changed here. */
   c->current_N = p->proposed_N;
   c->trial_active = true;
   c->trial_wins = c->trial_unknowns = 0;
   return NF_A840_TRIAL;
}

/* A/B evidence: all savings must exceed measured overhead + noise.
 * Strict subtraction avoids unsigned addition overflow. */
static inline bool
nf_a840_profitable(const struct nf_a840_trial_evidence *e)
{
   if (!e->comparable || e->paired_samples < 3 ||
       e->baseline_ns <= e->candidate_ns ||
       e->candidate_p95_ns > e->baseline_p95_ns)
      return false;
   uint64_t savings = e->baseline_ns - e->candidate_ns;
   if (savings <= e->decision_cpu_ns) return false;
   savings -= e->decision_cpu_ns;
   if (savings <= e->transition_cpu_ns) return false;
   savings -= e->transition_cpu_ns;
   if (savings <= e->inference_amortized_ns) return false;
   savings -= e->inference_amortized_ns;
   return savings > e->noise_margin_ns;
}

static inline enum nf_a840_result
nf_a840_record_trial(struct nf_a840_controller *c,
                      const struct nf_a840_trial_evidence *e)
{
   if (!e->correctness_ok) return nf_a840_safety_stop(c);
   if (!c->trial_active || c->safety_blocked) return NF_A840_REJECT;
   if (nf_a840_profitable(e)) {
      c->trial_unknowns = 0;
      if (++c->trial_wins >= c->cfg.wins_to_accept) {
         c->safe_N = c->current_N; /* verified in this compatibility domain */
         c->trial_active = false;
         return NF_A840_ACCEPT;
      }
      return NF_A840_NO_CHANGE;
   }
   c->trial_wins = 0;
   /* Confirmed tail regression: exit immediately, no statistical waiting. */
   if (e->comparable && e->paired_samples >= 3 &&
       e->candidate_p95_ns > e->baseline_p95_ns) {
      c->current_N = c->safe_N;
      c->trial_active = false;
      ++c->fallbacks;
      return NF_A840_FALLBACK;
   }
   if (++c->trial_unknowns >= c->cfg.unknowns_to_fallback) {
      c->current_N = c->safe_N;
      c->trial_active = false;
      ++c->fallbacks;
      return NF_A840_FALLBACK;
   }
   return NF_A840_NO_CHANGE;
}

/* New context requires a caller-verified baseline and fresh controller.
 * Never transplant timings or safe_N across compatibility domains.
 */
#endif /* NF_A840_TEMPORAL_H */
