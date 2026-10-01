# Drnas Turnip V66 — A810 WIDE-LAB

V66 starts a new phase: optimize and validate the driver across several engines,
DXVK generations and FEX versions instead of tuning one Crysis frame.

Base: the proven V61 SIGNATURE-GATED-SCAN stack.

## Module 1 — SHADER-BALANCE

V25 taught us that a small fixed A810 scheduler window can be excellent in
Far Cry 2, but a single fixed maximum is unlikely to be optimal for every
shader in every engine.

V66 keeps the existing IR3 live-pressure estimator and changes only the
A810 pre-RA SY/texture window when `TU_FRANE_SHADER=1`:

- pressure < 12%: window 6
- pressure < 25%: window 4
- pressure < 45%: window 3
- pressure >= 45%: window 2

The idea is to expose extra memory-level parallelism only in genuinely cheap
blocks, then collapse quickly toward occupancy as live register pressure rises.

`TU_FRANE_SHADER=0` restores the exact V61/V25 scheduler policy.

The new shader toggle is included in both the Vulkan pipeline-cache identity
and IR3 disk-cache identity, so A/B runs cannot silently reuse binaries compiled
under the other policy.

## Module 2 — SIMPLE-COLOR-RESOLVE

Our downstream GMEM safety gate has intentionally blocked every resolve/MSAA
pass since V26. Mesa/Turnip itself has a native GMEM color-resolve path, so V66
opens one deliberately narrow class behind `TU_FRANE_RESOLVE=1`.

Allowed:
- one subpass, full-frame, single-layer existing safety envelope;
- color-only resolve;
- 1 or 2 resolve attachments;
- 2x or 4x MSAA;
- resolved multisample sources only.

Still blocked:
- depth/stencil resolve;
- unresolve;
- custom resolve;
- input attachments;
- feedback loops;
- conditional load/store in the resolve pass;
- multiview/FDM/MSRTSS;
- 8x+ MSAA;
- any depth/stencil attachment in the opened class.

V66 does not implement a new resolve shader or packet sequence. It only stops
our downstream safety gate from forcing this narrow class to SYSMEM and lets
Mesa's existing Turnip GMEM resolve implementation execute.

`TU_FRANE_RESOLVE=0` restores V61 resolve blocking.

## Why both modules are in one lab build

This build is designed for the new broad test matrix. The two modules are
independent switches, so the same binary can test:

- both ON (default);
- shader only;
- resolve only;
- exact V61 behavior for both new modules OFF.

That makes FEX/DXVK/game interaction testing practical without producing four
separate drivers.

## First-pass test set

Use several engines, not only Crysis. Keep a V61 control and record at least
warm average, minimum/1% low where available, frametime feel, RAM, artifacts,
and crashes.

Suggested first sweep:
- Crysis / CryEngine 2;
- Far Cry 2;
- Far Cry 3;
- Dirt 3 or GRID 2;
- one MSAA-capable title to exercise the new resolve class.

This is an experimental performance build, not a new reference release.
