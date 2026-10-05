# A810 S4 Max — internal draft

S3-based A810 experiment with four GMEM packing seeds, lifetime peak capacity bound, gap-aware track fitting and a 16384-node search budget. IR3 gains pressure-driven SY/SS windows and bounded critical-path ranking; the default texture window becomes 6.

Every new method has a TU_FRANE switch. All effective compiler controls are hashed into shader-cache schema v2. The proven A810 CCU layout, LRZ, synchronization, overflow handling and final GMEM eligibility checks are retained.

See A810-S4-Max-Tuning.md for defaults, A/B settings and test limits. Installable ZIP contains the ARM64 KGSL Vulkan library and metadata. Source ZIP includes the pinned patch stack, tests and CI logs. This remains an internal draft. No device FPS gain is claimed.
