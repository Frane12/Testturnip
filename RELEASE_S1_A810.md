# Drnas-Turnip S1 A810

**Status:** Stability / Endurance candidate  
**Target:** Adreno 810 · Android ARM64 / KGSL  
**Base:** Mesa 26.3.0-devel snapshot

S1 marks the point where the A810 branch moves from short benchmark tuning into longer real-game validation. The render policy is intentionally frozen so stability can be evaluated without changing the driver between sessions.

## Current driver state

- **PROFILED Tail Guard** keeps expensive or ambiguous GMEM tail cases from being blindly forced and can return the decision to Mesa PROFILED.
- **Tail Learner** uses bounded GMEM/SYSMEM timing evidence and only acts after enough paired data exists.
- **Frequency-Aware Scan** limits exploration according to render-pass recurrence so rare work does not pay unnecessary learning cost.
- **Signature-Gated Scan** avoids forced scan overhead on cold/rare render passes and uses scanning mainly as a rescue/completion path for genuinely recurring work.
- **GMEM safety, depth handling, scheduler and command-buffer tuning** remain active in the current A810 stack.
- **Mesa PROFILED autotuner is recommended.** The Drnas policy is designed to cooperate with it and defer when confidence is insufficient.
- Normal S1 use requires **no manual `TU_FRANE_*` overrides**.

## Experimental game adaptation

`TU_FRANE_PROFILE_ID` is an **experimental profile/adaptation hook** intended for controlled game/workload-specific tuning. It is not part of the recommended S1 endurance default and should be treated as experimental while profile behavior is being evaluated across different games.

## Phase

- Performance tuning: **frozen for S1**
- Short benchmark repeatability: **passed**
- Policy / safety CI tests: **passed**
- Android ARM64 compile: **passed**
- AdrenoTools ZIP verification: **passed**
- Long-session endurance validation: **in progress**

## Endurance focus

S1 is now being evaluated for:

- RAM growth during long sessions;
- frametime drift after warm-up;
- hangs, freezes or device-lost events;
- intermittent visual corruption or artifacts;
- behavior across level / scene changes;
- whether learned GMEM/SYSMEM decisions remain sensible as workload changes.

## Recommended reference setup

- Renderer: **System / FIFO**
- Vulkan present mode: **MAILBOX**
- Autotuner: **PROFILED — recommended**
- FEX: **2609**
- DXVK: **1.9.4**
- `TU_FRANE_*`: **default / no manual overrides**

S1 is the first **stability/endurance milestone** after the performance-tuning phase. It is not being presented as the final stable endpoint yet.
