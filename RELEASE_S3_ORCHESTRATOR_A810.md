## Turnip-Drnas A810 S3 Orchestrator — internal experiment

Built on the user-validated S2.1 Render Recovery stack and pinned Mesa
eda9aceb39d5ff169b096444abe366bdf2269e24.

S3 adds one owner for render-mode selection and timestamp requests on eligible
A810 one-time PROFILED renderpasses. Fresh GMEM/SYSMEM samples carry an exact
pair tag, preventing unrelated samples from being combined. A bounded,
normalized advantage average and deviation penalty determine when a pattern
has enough evidence to retain its winner. Periodic winner probes detect cost
changes and reopen learning; stable patterns bypass the legacy selector chain.

The CPU path uses one packed atomic decision snapshot, no recording-time clock,
shared RNG or new GPU waits. Feedback state adds 80 bytes plus an 8-byte snapshot
per existing history object. Controller history is process-local, not a new
persistent disk model. Dormant legacy learners do not consume S3-owned samples.

S3 also exposes bounded controls for CB admission, an optional configurable CB
keep gate, texture-prefetch stages, UBO locality and scheduler texture window.
Compiler options remain part of the shader-cache key. Default shader settings
and CB thresholds match S2.1; the controller is the default experiment.

The pre-S2 A810 CCU values, actual GMEM allocator, LRZ implementation, KGSL clock
policy, GPU synchronization and final GMEM safety checks are retained.
The new controller can consider up to 64 estimated tiles by default, but it
cannot bypass the final safety gate or increase hardware memory capacity.

Three presets: balanced (default), throughput, and fluidity. Set
TU_FRANE_ORCH=0 to return to the S2.1 decision path; remove optional compiler/CB
overrides as well for a full default comparison. See the tuning guide.

Validation: source-stack reproduction, baseline Smart v2 tests, new controller
tests under UBSan and ASan/UBSan, tagged-pair reordering and duplicate handling,
counter rollover, 64-bit duration extremes, noisy and tiny passes, drift,
configuration/layout boundaries, and 400000 fuzzed pairs. In the deterministic
balanced simulation, stable measurement requests were 156/19999 and a mode-cost
reversal at occurrence 25000 was recognized at occurrence 25185. These are
synthetic policy results, not Android FPS or frametime measurements.

Internal draft only. On-device render correctness, speed, lows, smoothness,
temperature, power and RAM remain to be measured against S2.1, using the same
FEX, DXVK, resolution, affinity and game settings.

Measurement reference: https://docs.vulkan.org/samples/latest/samples/api/timestamp_queries/README.html

