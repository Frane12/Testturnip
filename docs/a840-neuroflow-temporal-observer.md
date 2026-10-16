# A840 NeuroFlow: Temporal Observer v0.1 (next-build preparation)

**Status:** isolated experimental source, **NOT ACTIVE in released A840 H2.8 binary**. No NPU access, QNN/HTP runtime, Mesa render-path integration, GPU benchmarks, or A840 on-device validation is claimed. This branch was based on `feature/neuroflow-decision-debt-v01` rather than silently altering `main`, other chip variants, or the TESTING ONLY prerelease.

## Decision agreed for the first experiment

**CPU retains the wheel. NPU is an OBSERVER only.** Use available render-pass telemetry on arrival, detect meaningful *changes over elapsed time (dT)*, and copy bounded event history to a later asynchronous NPU backend. No fixed-rate NPU sampling, no profile/game ID, and never block the GPU on inference. Even a supposedly 99.9%-confident NPU response is recorded as shadow-only in default mode.

1. **Event-driven input:** `nf_a840_observe` accepts an externally timestamped completed observation, and stores an event only after a workload fingerprint change or a sufficiently large difference in an already available timing metric. It does **not** query GPU counters or a clock. No periodic calls are required. This is a filter, not a claim of statistical independence.
2. **Temporal pattern:** an immutable request consists of up to 12 chronological events, including their `dt_ns`, signature/pattern fingerprint, and measured cost if previously available. NPU prediction learns from the *evolution of behavior*, not `PROFILE_ID`.
3. **Asynchronous boundary:** `nf_a840_take_request` snapshots the bounded history. `nf_a840_npu_port.h` defines a future nonblocking transport. A worker must deep-copy requests and return predictions via a thread-safe queue to the CPU controller owner. There is **no actual NPU connector yet**.
4. **CPU safety gate:** `nf_a840_offer_prediction` rejects unknown, expired, out-of-range, low-confidence, compatibility-mismatched and superseded responses. With default mode `NF_A840_OBSERVER` all valid suggestions are SHADOW ONLY: `current_N` does not change.
5. **Later SUPERVISED experiments only:** Requires **both** setting `allow_supervised=true` in config and a separate explicit `nf_a840_set_mode(..., NF_A840_SUPERVISED)`. Only then can a suggestion enter a provisional N trial. It never changes actual Vulkan render state; integration must respect legal pass boundaries, Mesa correctness guards and external synchronization.
6. **Validation and fallback:** `nf_a840_record_trial` requires paired comparable reference/candidate windows and CPU decision, transition and amortized inference overhead. Three wins accept the candidate as `safe_N`; a confirmed p95 tail regression falls back immediately; two inconclusive windows also revert. A correctness fault hard-latches the custom controller off, leaving the host responsible for Mesa-safe fallback.

### Crucial correctness rule

**Workload pattern similarity is NOT render-pass compatibility.** `compatibility_key` is a *caller-validated safety domain*, distinct from `pattern_key` used for prediction. Do not share controller state, learned winners, depth/stencil/attachment assumptions or timing evidence between incompatible render passes. A per-compatible-signature controller or reset with a freshly verified safe N is required. A game/app name is never a substitute for this key.

### Cost accounting

A plausible candidate requires *measured*, matched A/B savings:

```
latency_saved > decision_cpu_cost + transition_cpu_cost
              + amortized_inference_cost + measured_noise_margin
```

This is a screening heuristic. CPU and GPU execution overlap, inference has energy/thermal cost, and there may be effects on p95/p99 tail frame time. Only full-stack on-device A/B tests establish real improvement. A neural model is NOT automatically faster or more accurate than a cheap CPU change detector. Compare against observer-disabled baseline.

### Entry points for future integration

- `include/nf_a840_temporal.h`: portable allocation-free C11 state machine; no hardware assumptions and no locks. Owned by one thread.
- `include/nf_a840_npu_port.h`: deferred asynchronous NPU transport contract; **not** a QNN implementation.
- `tests/test_nf_a840_temporal.c`: event filtering, ring ordering, shadow defaults, missing NPU protection, stale-epoch rejection, explicit supervised trials, acceptance, tail regression, safety latch, overflow.
- `.github/workflows/a840-neuroflow-temporal.yml`: native C11 unit test + sanitizers. Passing does not certify Android/Turnip support.

Proposed Mesa integration **after** tests, A840 source compatibility, and controlled device data:

```text
existing completed pass feedback
           |
cheap event filter (CPU) -> bounded temporal events
           |                       |
       safe Mesa policy         worker queue -> QNN/HTP (later)
           |                       |           |
     GPU runs unblocked          predicted N + request/epoch metadata
           |                                   |
   known-safe current N   <- CPU gate <- response queue
           |                          default: SHADOW ONLY
   (later explicit trial)  -> A/B compare -> accept or safe fallback
```

Do not call the NPU runtime, take a mutex, malloc, wait, or do fresh GPU timestamp queries in the render hot path. If inference stalls, the host must continue using the verified Mesa policy. If the input stream has no new meaningful events, NPU runs zero additional inference jobs. A provisional **250 ms minimum gap between event-triggered jobs** also prevents bursts; it is a throttle, NOT periodic sampling. Both the gap and event thresholds require measurement-based tuning on A840.

### Next session: accessing Qualcomm NPU

1. Verify exact A840 device/SOC model, firmware permissions and available QNN/HTP runtime interfaces. Hexagon accessibility is *not* assumed.
2. Implement a standalone, independently benchmarked asynchronous QNN smoke test (tensor in, tensor out), outside Mesa first.
3. Establish measurement of end-to-end enqueue/compile/inference cost, CPU wakeups, energy/thermal effects and stale-completion behavior.
4. Compare cheap CPU statistical predictor vs NPU temporal model on the SAME captured event traces.
5. Only then consider adding an A840-specific Mesa integration hook behind **default-off**, separately validated experimental flags.

**Do not publish these reference-only changes as a working NPU-enabled GPU driver.**
