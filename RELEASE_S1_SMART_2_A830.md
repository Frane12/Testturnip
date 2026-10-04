# Drnas-Turnip S1 A830 — Smart Performance

**Status:** Public experimental / A830 performance branch  
**Target:** Adreno 830 · Android ARM64 / KGSL  
**Base:** Mesa 26.3.0-devel snapshot + Drnas A830 RC1 stack

S1 A830 is the Smart Performance branch for the stronger A830 target. The goal is not power-max or forced clocks; it is to make the render path spend less time re-deciding the same GMEM/SYSMEM situations while keeping hard safety gates around GMEM.

## Default behavior

**Guarded A830 GMEM is enabled by default.**

`TU_FRANE_A830_GMEM=0` disables the A830 GMEM path and returns those passes to SYSMEM.

This does **not** blindly force every render pass into GMEM. With the default enabled, a pass must still satisfy the A830 safety scope before the normal/Smart selector is allowed to choose GMEM. Unsupported or suspicious passes remain on SYSMEM.

`TU_FRANE_SMART=0` disables the Smart scene-history layer and falls back to the existing selector.  
`TU_DEBUG=sysmem` remains an explicit forced-SYSMEM control.

> **Important:** A830 GMEM write page faults have been reported in community/mainline drivers. This build adds bounds/scope protection and the latest reviewed fixes, but it does not claim that the underlying hardware/firmware page-fault issue is proven solved. The public build is therefore marked experimental.

## Smart scene memory

Repeated render patterns no longer need to pay the full decision cost every time. S1 stores bounded history and promotes patterns through four confidence tiers:

| State | Evidence | Behavior |
|---|---|---|
| COLD | insufficient / stale paired evidence | one GMEM/SYSMEM control pair per 8 recurrences; otherwise base selector |
| WARM | confidence ≥ 4/8 and ≥ 8 fresh pairs | remembered winner; 2 measurements per 64 recurrences |
| TRUSTED | confidence ≥ 6/8 and ≥ 12 pairs | 2 measurements per 128 recurrences |
| LOCKED | confidence 8/8 and ≥ 16 pairs | 2 measurements per 256 recurrences |

The A830 history key includes render area, render-pass structure, draw-count bucket and GMEM layout so a materially different scene does not inherit an old answer. Strong contradictory evidence can demote or reverse a learned decision; stale history expires.

The Smart helper itself adds no new mutex, wait, timer or per-decision allocation. Decision ownership and measurement ownership stay single-path to avoid duplicate work.

## A830 GMEM safety scope

Before an A830 pass is allowed to use the experimental GMEM path, the driver checks:

- A830 GPU ID gate;
- one layer / one view;
- no FDM or MSRTSS;
- no MSAA or resolve path in the guarded scope;
- physical and usable GMEM limits;
- tile-pixel limits;
- attachment offset/end bounds;
- separate D32S8 stencil range;
- CCU/VPC cache-reservation arithmetic before unsigned subtraction;
- custom depth/stencil resolve exclusions.

If any guard fails, the pass falls back to SYSMEM.

## Included driver work

- Smart GMEM/SYSMEM scene-memory policy adapted for A830.
- A830-specific history signature and lower-frequency re-probing once confidence is established.
- Retained A830 V59 LRZ-CLEAN logic.
- Mesa `CmdClearAttachments` GMEM blit-write access/barrier fix.
- KGSL fixed-address `munmap` cleanup.
- ION handle/fd allocation-failure cleanup.
- KGSL dma-buf import cleanup on `GPUOBJ_INFO` failure.
- Existing suballoc NULL cleanup retained.
- No clock unlock, no thermal-governor bypass and no A810 power-max path.

## Controls

```
TU_FRANE_A830_GMEM=1   # default; enable guarded A830 GMEM eligibility
TU_FRANE_A830_GMEM=0   # disable A830 GMEM path / use SYSMEM fallback
TU_FRANE_SMART=1       # default; Smart scene history enabled
TU_FRANE_SMART=0       # disable Smart history, keep existing selector
```

For normal testing, leave the variables unset first. Use `TU_FRANE_A830_GMEM=0` as the clean comparison / recovery control if you see a page fault, device-lost event, hang or rendering corruption.

## CI / host validation

Executed for this branch:

- **716,040 Smart-policy combinations** across confidence, pair counts, PROFILED boundaries, tail risk, instability and both winners;
- freshness, reused/old sample rejection, completion-order inversion, uint32 rollover, ties, saturation and UINT64_MAX;
- cadence and moving probe position across 128 blocks;
- synthetic regime change at occurrence 4096;
- **830 A830 GMEM arithmetic cases** against an independent 128-bit oracle;
- A830 history-key construction with render-area / pass / draw-bucket / layout separation;
- ASan + UBSan host tests;
- source-order / safety-gate / KGSL cleanup checks;
- full Android ARM64 NDK r29 Turnip build;
- ZIP integrity, ELF64 AArch64 identity and runtime-option verification.

## Device validation status

Not yet claimed as completed: Vulkan CTS on A830 hardware, long-session game endurance, FPS/frametime/temperature measurements, or proof that the known A830 GMEM write page fault cannot occur.

Please report the game, Winlator/Ludashi build, FEX/Box64 version, DXVK version, resolution, and whether `TU_FRANE_A830_GMEM=0` changes any fault or artifact.

---

Built from the dedicated **`drnas-a830-s1-smart-performance-2`** branch.

AI provenance: Generated-by: LLM.
