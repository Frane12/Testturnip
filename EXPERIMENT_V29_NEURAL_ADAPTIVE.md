# Frane Turnip V29 Neural Adaptive CLEAN (experimental)

Base: V28 CLEAN dcf0ca3749385c2e1ae68eb01cad46515e254a55, Mesa 26.2.3
31e9a6b2e95e30d84bf3177d1f497d063e59b6b2. Android ARM64, API 34+.

## Install / defaults
Import the driver ZIP into the same Winlator/Bannerlator container as V28.
For a clean comparison, remove previous TU_AUTOTUNE_ALGO, TU_AUTOTUNE_FLAGS,
TU_DEBUG and custom tuner overrides. Keep the same FEX, DXVK, resolution and
other settings. Set only this environment variable if the application name is
generic or if you want a reproducible profile name:

```
TU_FRANE_PROFILE_ID=FarCry3
```

Use a distinct name per game. This is a cache identity, not a hand-tuned game
preset. The old TU_A810_PROFILE_ID remains accepted. PROFILED, adaptive sampling,
lean instrumentation, profile persistence and neural learning are enabled by
default. Explicit algorithm/environment overrides and application drirc policy
still take precedence. Universal PROFILED now also supersedes the old implicit
A830 BANDWIDTH default; A830 requires separate hardware validation.

## Changes
- Actual online neural network: 8 inputs, hidden layers of 12 and 8 leaky-ReLU
  neurons, one signed timing-advantage output; 221 learned parameters, 900 bytes
  of model state per Vulkan device. Pure C++, no ML libraries, NPU or GPU jobs.
- Features: framebuffer width, height, layers, attachment count, SYSMEM/GMEM
  per-pixel bandwidth estimates, GMEM tile pixel capacity, initial draw count.
- SGD backpropagation through both hidden layers, clipped gradients/weights.
  Labels come only from GPU-measured durations. Each RP needs eight fresh
  observations of EACH mode for another update; at most one device-wide update
  per 2 ms. No training on recording threads. Nonblocking model lock; skip on
  contention. One forward pass only when creating a history without a cache hit.
- At least 64 updates and pre-update EMA prediction error 20% below the neutral
  baseline are needed before a neural hint is used. Neural hints only bias a
  new history 40/60 and cannot lock a mode or bypass Mesa render safety rules.
  Live PROFILED measurements then take over. V28 conservative lock policy is
  retained; the neural component does not reopen those locks.
- Atomic sampling-interval snapshots replace concurrent reads of submit-owned
  counters/warmup state. Atomic counter hashing replaces a shared mutable RNG.
- Profile reads and neural prediction happen outside the exclusive RP-map lock.
- Persistent locked winners are saved as weak 40/60 priors. A neutral 50 remains
  neutral; malformed cache data and invalid neural weights are rejected.
- Zero-duration observations and probability-lock division overflow guarded.
- Device-specific defaults no longer leak through a process-global once flag.
- Per-game neural model and RP priors use Mesa disk cache, isolated by GPU,
  driver cache UUID and V29 schema. Model saves are throttled to 60 s and also
  attempted on orderly destruction. RP priors retain the 60 s per-RP throttle.

## Preserved baseline / limits
The removed A810 custom GMEM runtime and forced MAILBOX stay removed. Normal
Mesa GMEM rendering remains available. Existing shader/image, KGSL power,
allocation and fence lifetime behavior remain from the CLEAN base. Diagnostic
flags are not indiscriminately enabled.

This is a small deep online regressor experiment, NOT a pretrained game model,
NeuralUCB implementation, or proven FPS improvement. Error gating is an online
heuristic, not an independent accuracy guarantee. Initial render-pass features
and stable image creation IDs may vary across scene loads; restored knowledge
is deliberately weak and remeasured. A cache write requires a writable Mesa
cache in the emulator; without it, current-session learning still works but
cannot survive process restart. Profiles are invalidated when the build UUID
changes. No per-device hardware testing was performed by the build environment.

## Validation / A-B test
The workflow runs numerical gradient checks for every parameter, online
learning and preference reversal, cache corruption/bounds checks, randomized
decision distribution checks, and existing policy tests under sanitizers.
It builds the real Android AArch64 .so and checks ZIP/ELF metadata, source diff
and checksums. This verifies code/build properties, not mobile game performance.

Compare V28 CLEAN versus V29 with identical settings, cooling and scene.
Measure 10-15 minutes, then fully restart the game to test persistence. Record
FPS/frametime, RAM and artifacts. Optional diagnostic comparison:
TU_FRANE_NEURAL=0 disables only neural learning/hints while retaining V29 fixes.

Background references (not imported implementations):
https://docs.mesa3d.org/drivers/freedreno.html
https://proceedings.mlr.press/v119/zhou20a.html
