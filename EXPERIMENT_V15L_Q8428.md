# V15-L / Adreno 842.8 memory-management experiment

Base (preserved, unmodified): `mesa-26.1.4-v15k-smart-gmem-stats` at `7b8ab18b6ceafec13d834328d0ea48f87b2cbf65`. New experimental branch: `mesa-26.1.4-v15l-a830-q8428-guard`.

## Evidence and limits

User-supplied `adreno-driver-842.8.zip` is an AdrenoTools package containing `vulkan.adreno.so`, `libgsl.so`, gralloc libraries and metadata ("Version 842.8, extracted from Gamehub"). Inspecting its exported symbols reveals `gsl_command_freememontimestamp_pure`, `gsl_syncobj_wait`, and `gsl_memory_free_pure`. The Vulkan binary contains the string `Low Draws, Gmem Load`. These are **clues, not documentation of proprietary algorithms**, and do not prove that Turnip can reproduce Qualcomm's memory-management implementation. Do not link or redistribute those blobs into Turnip.

## Implemented

- Keep V15-K A830 350 ms Android MemAvailable sampling, memory-tier hysteresis, per-RP atomic confidence, 12.5%+ tile/caution margins, gralloc fallback and memory-budget/pool changes.
- Keep ALL Mesa synchronization, BO ownership, GPU fence/timestamp, attachment load/store and resolve behavior unchanged. No attempted forced freeing, no extra BO allocations.
- When the optional Q8428 tuning is on: for 7–12 tiles with fewer than two draws per tile, require an additional 1% modelled GMEM-traffic saving. When GMEM is already confirmed for that RP, there are at least three draws per tile, and memory tier is healthy, relax V15-K's tile penalty by at most 1.6 percentage points. A new renderpass must still meet the original V15-K entry margin.
- Fix a potentially overflowing *legacy V15-J A/B* `gmem_bw*8 <= sysmem_bw*7` comparison using mathematically identical division/remainder.
- Extend opt-in 5-second diagnostic with Q8428 selector, density decision and bandwidth model.

**A/B env flags (restart container/game between tests):**

| Flags | Interpretation |
|---|---|
| default | V15-L Q8428 cost model |
| `TU_A830_Q8428_POLICY=0` | V15-K tuning, with overflow-safe legacy check |
| `TU_A830_SMART_GMEM_STATS=0` | V15-J selector |
| `TU_A830_SMART_GMEM=0` | V15-G control |
| `TU_A830_SMART_GMEM_LOG=1` | expensive diagnostic output at most once per 5s, do not enable for performance comparisons |

## Field test plan

Compare default V15-L vs `TU_A830_Q8428_POLICY=0` while **holding all other Winlator/Bannerlator, resolution (1280×720), texture quality, FEX, DXVK, FPS lock, Turnip and Android settings fixed**. Test same FC4 scene for 15+ minutes; inspect 1% low FPS, frame-time variance, RAM trend and any color/depth artifacts. Repeat switching A/B/A to distinguish cache warm-up. If tearing, artifacts or memory rise, revert to V15-K or disable Q8428. GPU page faults require KGSL fault logs and cannot be diagnosed from Vulkan selector metrics alone.

The default does **not** assert RAM reductions or FPS improvements; GMEM is hardware-local and choosing SYSMEM may *increase* system traffic/allocations. A successful cross compile proves packaging, not device runtime correctness.
