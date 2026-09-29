# Drnas Turnip V44 — THROUGHPUT-CB

V44 goes after a much larger lever than the V40–V43 CPU micro-fastpaths:
**A810 BV/BR overlap through Turnip concurrent binning**.

Mesa already contains the A7XX+ concurrent-binning machinery, including dynamic
barrier patching, LRZ guards, resource-overflow handling and BV/BR count
synchronization.  However, Mesa's DRI option leaves it **disabled by default**
because broad enablement can regress desktop-game workloads.

V44 does not invent new A810 registers and does not remove synchronization.
Instead it selectively exposes that existing hardware/software path on A810.

## V44 policy

The custom A810 override is on by default, but a renderpass only gets concurrent
binning when it is heavy enough to amortize the setup cost.

Default threshold:

```
TU_A810_26344_CB_MIN_DRAWS=8
```

More aggressive experiment:

```
TU_A810_26344_CB_MIN_DRAWS=4
```

Exact V42 CB policy:

```
TU_A810_26344_SMART_CB=0
```

**Important:** `TU_DEBUG=nocb` still disables concurrent binning. Remove
`nocb` when testing V44, otherwise the experiment is intentionally bypassed.

## What remains untouched

V44 retains all existing Turnip CB correctness gates and synchronization:

- LRZ fast-clear requirements
- partial LRZ fast-clear protection
- BV/BR resource-overflow handling
- query-driven dynamic CB disable
- CB barrier patchpoints
- BV waits for BR and BR waits for BV
- V39 GMEM-PRESSURE baseline
- V42 draw-cache changes

The experiment is therefore about increasing **pipeline throughput by overlap**,
not skipping required waits.

## Benchmark

Use the same Crysis 32-bit / 4-strongest-core / three-pass protocol.

Current non-CB reference from this session:
- warm passes: 33.61 / 33.79 FPS
- warm mean: 33.70 FPS
- minimum: 21.86 FPS

V43's 33.36 / 33.27 result is not the baseline for V44; V44 branches from V42.
