# Frane Turnip V24 — A810 Lean Hotpath (experimental)

V24 forks [V23 A810 Lean WSI](../mesa-26.2.3-a810-v23-lean-wsi)
without changing V18, V22 or V23. Pinned **Mesa 26.2.3**
`31e9a6b2e95e30d84bf3177d1f497d063e59b6b2` for
Android ARM64/KGSL/Winlator.

The DiskDVD A810 descriptor-prefetch workaround, V18 sampled-depth option,
V22 profiling, V23 embedded MAILBOX WSI preference and V16 memory
ownership remain unchanged. V24 attempts three narrow CPU optimizations:

- avoid xorshift/modulo when plain PROFILED has irreversibly locked to 0/100;
- avoid sample-interval lookup when every renderpass is measured anyway;
- avoid mapped fence reads on submissions with no queued autotune results.

`TU_A810_V24_FASTPATH=0` restores V23 behavior within the V24 binary.
**This is not a new Vulkan layer, GL renderer or proven FPS improvement.**

See [audit / experiment / rollback](EXPERIMENT_V24_A810_LEAN_HOTPATH.md).

## Build

The branch's GitHub Actions workflow runs on push, validates V22/V23/V24
host tests and cross-compiles real AArch64 Turnip. After success the
AdrenoTools ZIP is `Frane-Turnip-Mesa-2623-A810-V24-LEAN-HOTPATH.zip`.
GitHub release tag: `v24-a810-lean-hotpath`. Download the ZIP, not
`mesa-applied.patch`, for Winlator. Keep V18/V22 for recovery;
never replace the system/vendor Vulkan driver.
