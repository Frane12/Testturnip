# Drnas-Turnip S1 A810

**Status:** Stability / Endurance candidate  
**Target:** Adreno 810 · Android ARM64 / KGSL  
**Base:** Mesa 26.3.0-devel snapshot

S1 marks the point where the A810 branch moves from short benchmark tuning into longer real-game validation. The render policy is intentionally frozen for this release so stability can be judged without changing the driver between sessions.

## Current driver state

- **PROFILED Tail Guard** protects expensive or ambiguous GMEM tail cases and can return the decision to Mesa PROFILED instead of hard-forcing a mode.
- **Tail Learner** uses bounded GMEM/SYSMEM timing evidence and only acts after enough paired measurements exist.
- **Frequency-Aware Scan** limits exploration according to render-pass recurrence.
- **Signature-Gated Scan** avoids unnecessary forced probing on cold or rare render passes and uses scanning mainly as a rescue/completion path for recurring work.
- **GMEM safety, depth handling, scheduler and command-buffer tuning** remain active in the current A810 stack.
- **Mesa PROFILED autotuner is recommended and should remain enabled.** The Drnas policy is designed to cooperate with it and defer when there is not enough reliable evidence for an override.
- No extra `TU_FRANE_*` variables are required for normal S1 use.

## Phase

- Performance tuning: **frozen for S1**
- Short benchmark repeatability: **passed**
- Policy / safety CI tests: **passed**
- Android ARM64 compile: **passed**
- AdrenoTools ZIP verification: **passed**
- Long-session endurance validation: **in progress**

## Endurance focus

S1 is now being judged mainly on:

- RAM growth over long sessions;
- frametime drift after warm-up;
- hangs, freezes or device-lost events;
- visual corruption or intermittent artifacts;
- behavior across level and scene changes;
- whether learned GMEM/SYSMEM preferences remain sensible as workloads change.

## Recommended reference setup

- Renderer: **System / FIFO**
- Vulkan present mode: **MAILBOX**
- **Autotuner: PROFILED — recommended**
- FEX: **2609**
- DXVK: **1.9.4**
- `TU_FRANE_*`: **default / no manual overrides**

S1 is not labeled final stable. It is the first **stability/endurance milestone** after the performance-tuning phase.
