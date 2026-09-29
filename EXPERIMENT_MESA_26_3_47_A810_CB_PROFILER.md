# Drnas Turnip V47 — CB-PROFILER

V47 turns the concurrent-binning heavy-pass bypass into a controlled profiler
instead of adding another opaque threshold.

The Crysis A/B established two useful facts:

- exact V45-style behavior is fast and highly repeatable;
- V46's broad additive pressure score can improve isolated peaks but lowers
  warm-run throughput overall.

So the V47 default is the known-good V45 keep policy, and one environment
variable selects a narrowly defined experiment.

## Profile modes

```
TU_A810_26347_CB_PROFILE_MODE=0
```
Pure Turnip runtime feedback. No static heavy-pass bypass.

```
TU_A810_26347_CB_PROFILE_MODE=1
```
Exact V45 heavy-pass keep policy. **Default / reference.**

```
TU_A810_26347_CB_PROFILE_MODE=2
```
V45 heavy-pass set filtered by `avg_bw >= 16`. This tells us whether the
low-bandwidth members of V45's first arm are unnecessary.

```
TU_A810_26347_CB_PROFILE_MODE=3
```
Balanced three-way gate. Draws, tiles and bandwidth must all be substantial;
one giant metric cannot compensate for weak values in the others.

```
TU_A810_26347_CB_PROFILE_MODE=4
```
Exact V46 pressure policy for regression/reference.

```
TU_A810_26347_CB_PROFILE_MODE=5
```
Ultra-heavy upper-envelope probe only.

## Structural telemetry

Optional:

```
TU_A810_26347_CB_PROFILE_LOG=1
```

This emits compact `A810-CB47` lines with:

- draws
- tile count
- average per-draw bandwidth estimate
- V45 adaptive admission threshold
- bounded pressure score
- V45 keep decision
- V46 keep decision
- selected mode decision

Do **not** use profile logging for FPS comparison; log I/O can perturb CPU
timing. Use it only once after the fastest profile mode has been identified.

## Test order

The efficient sequence is mode 1 -> mode 0 -> mode 2 -> mode 3. Mode 4 is
already characterized by V46 and mode 5 is only needed if mode 2/3 suggest that
benefit is confined to the upper tail.

Once adjacent modes stop producing a repeatable change in warm FPS,
triangles/sec or deterministic lows, CB policy is considered saturated and the
next work should move to another internal domain (MSAA/sample state, resolve
paths, bandwidth/state emission, etc.).
