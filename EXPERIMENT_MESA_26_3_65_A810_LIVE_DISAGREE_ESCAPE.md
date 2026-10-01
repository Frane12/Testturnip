# Drnas Turnip V65 — A810 LIVE-DISAGREE-ESCAPE

## Why this probe

The latest three-pass Crysis result stayed very repeatable but lost warm
throughput:

- Run 0: 31.80 FPS
- Run 1: 33.45 FPS
- Run 2: 33.29 FPS
- warm mean: 33.37 FPS
- repeated minimum: 21.52 FPS around frame 1955

Compared with the V61 reference (34.83 warm mean, 21.63 minimum), the important
signal is that globally reducing/reshaping exploration did not remove the late
deterministic tail and cost throughput.

So V65 stops touching probe cadence.

## Hypothesis

V58 stores a history-wide learned winner. At confidence 7-8 that winner is
allowed to overrule even a strong live Mesa PROFILED opinion. That is useful for
stable workloads, but it can be wrong for one unusually expensive scene phase
inside the same rp_history.

The late Crysis draw-distance/replay section is exactly the place to test that
without adding another moving average or per-RP state machine.

## Policy

V65 is built directly on V61.

Everything remains exact V61 unless all of these are true:

1. V57's depth/stencil tail-risk path is active.
2. Current replay work is >=640.
3. Current pass has >=80 draws or >=8 estimated tiles.
4. V58 is ready with |score| >=7.
5. V58 selected its learned winner, not a loser-control probe.
6. Mesa PROFILED strongly prefers the opposite mode:
   - learned GMEM winner + PROFILED sysmem probability >=75%, or
   - learned SYSMEM winner + PROFILED sysmem probability <=25%.

Only then V65 removes the learned override for that invocation and gives the
decision back to Mesa PROFILED.

## What V65 deliberately does not change

- V61 signature scan and recurrence logic
- V58 loser-probe frequency
- V58 winner refresh frequency
- learner state/update equations
- GMEM packing/layout
- LRZ, barriers, shaders, CB, WSI, MSAA/resolve or synchronization
- rp_history storage or atomics

There are no new counters, divisions, locks, allocations or loops.

## A/B

Default: `TU_FRANE_ESCAPE=1`

Exact V61 fallback: `TU_FRANE_ESCAPE=0`

First test: run the normal three-pass Crysis GPU TimeDemo with no extra
variables.

## What would count as useful evidence

Best case: warm mean returns toward V61 while frame ~1955 rises. That would say
the late tail is a phase-local mode disagreement rather than exploration
overhead.

If the result is essentially identical to V61, the late minimum is probably not
caused by the learned winner fighting PROFILED and we should move the next probe
away from selector policy into the actual tile/replay execution path.
