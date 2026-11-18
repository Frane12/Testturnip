# NeuroFlow Decision Debt — reference controller v0.1

> **The cost of intelligence must never outweigh the benefit of its decisions.**
>
> If selecting a faster path costs as much as it saves, the selector is not an optimization.

This is a **standalone, tested C11 reference implementation** for a future Turnip
policy hook: [`include/nf_decision_debt.h`](../include/nf_decision_debt.h). It is
**not wired into Mesa**, the S1/S2 driver binaries, or the Android build workflow.
No release FPS gain, reduced GPU time, or production-ready behavior is claimed.

## Why it exists

The existing Mesa PROFILED policy should remain the default safe path. A custom
GMEM/SYSMEM candidate should justify its extra CPU evaluation cost and any
strategy-transition cost using comparable, repeated A/B evidence. A fast strategy
can be a net regression if its scheduler spends too long deliberating.

For the same render-pass signature and comparable measurement window, define:

```
benefit = baseline_latency - candidate_latency
net_estimate = benefit - decision_cpu_cost - transition_cpu_cost
allow_evidence = paired_samples >= 3
              && comparable && correctness_ok
              && net_estimate > measured_noise_margin
```

Latency inputs are **wall-clock latency estimates excluding separately measured
policy overhead**, summed for matching A/B windows. They are not GPU timestamp
counters. These sums are an intentionally conservative screening heuristic,
**not** a mathematically exact prediction of frame latency: CPU and GPU work may
overlap. Only matched full-stack A/B game runs can establish a real improvement.
Record the noise margin from warm-run variation, not from a made-up constant.

## State machine

- **Probe**: inexpensive per-signature counter gates infrequent, more expensive
  custom policy evaluations. Default one eligibility check per 64 recurring
  occurrences; no clock read, heap allocation, atomic operation, or lock.
- **Unproven/negative windows**: after two consecutive losses, double the probe
  interval (capped at 1024) and cool down for 256 occurrences. An absent or
  incomparable A/B result is **unproven**, not a success.
- **Proven positive windows**: three consecutive profitable windows halve the
  interval down toward 64. The hysteresis prevents reacting to one outlier.
- **Correctness fault**: latch the custom evaluator off. Recovery requires an
  explicit reset after investigating the fault. The renderer must use its known
  safe path independently of this gate.

The module **does not** change the GMEM/SYSMEM decision, driver state, command
buffers, GPU scheduling, or synchronization. It only gates when higher-level
code *may* run an expensive policy evaluation. The caller must keep Mesa
PROFILED and the correctness guards authoritative. It must not apply a decision
halfway through a render pass or assume A810 parameters apply to A830/A840.

## Integration sketch (not integrated)

```c
/* Per *stable, recurring* render-pass signature, not global frame state. */
struct nf_debt_gate gate;
nf_debt_init(&gate, nf_debt_default_config());

/* Render-pass policy selection path: only one lightweight counter check. */
if (nf_debt_should_probe(&gate)) {
   /* MAY measure/compare a policy candidate at a legal decision boundary.
    * Respect all existing Mesa correctness guards and synchronization.
    * Do not collect expensive telemetry every frame.
    */
}

/* When a separate matched A/B evidence window has completed: */
struct nf_debt_evidence evidence = { /* measured paired results */ };
enum nf_debt_result result = nf_debt_record_window(&gate, &evidence);
if (result == NF_DEBT_SAFETY_STOP) {
   /* Use safe Mesa policy; investigate artifacts/validation failures. */
}
```

Each gate belongs to **one thread or otherwise externally synchronized owner**.
Never share/mutate a gate concurrently without integrating with existing lock
ownership; don't add a lock to the hot path just for this controller. Maintain a
small, capped per-signature table; low-frequency passes should avoid this gate.
On eviction or workload signature changes, reset the gate; stale evidence must
not be carried over to unrelated render passes. Validate `paired_samples` and
`comparable` at the measurement site; the gate can't establish statistical
comparability by itself. A conditional `should_probe` result is **not** permission
to change the current render mode without evidence or safety checks.

## Tests

```sh
cc -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
  -Iinclude tests/test_nf_decision_debt.c -o /tmp/test_nf_decision_debt
/tmp/test_nf_decision_debt
```

The unit tests cover probe spacing, backoff, cooldown, hysteresis, overflow-safe
net comparison, evidence minimum, correctness latch, and per-signature isolation.
Passing tests confirm the small state machine, **not** performance or Vulkan
correctness. Suggested A/B matrix for a real integration:

| Control | Candidate | Evidence required |
|---|---|---|
| Same Mesa base + PROFILED | PROFILED + gate | Identical scenes and settings; multiple warm runs |
| Gate disabled | Gate enabled | p50/p95/p99 frame times, 1% lows, FPS |
| A810 vs A830 | Same architecture-specific policy | No cross-device threshold reuse |

Also capture CPU time inside the evaluator, any mode-transition cost, 30/60 min
RAM, GPU fault counters, image/depth artifacts, device-lost events, temperature,
and cold/warm cache state. Keep max-frame-latency and present mode constant.

**Pass (for an integrated build):** no new correctness failures; measured
full-stack frame-time tails do not regress beyond the benchmark's run-to-run
noise; CPU evaluator overhead stays below the *measured* saving; benefits recur
in matched A/B runs. **Reject:** correctness failure, unstable oscillation,
unproven positive gain, or consistently worse p95/p99. A code compile alone is
not a pass.
