# Drnas Turnip A810 V38 SH1

Experimental Android ARM64 build for A810. Base: a810-v38-base,
4647153a15740979bdd60d2fd802a9fccce06c22. Mesa: eda9aceb39d5ff169b096444abe366bdf2269e24.

The V38 shader scheduler prioritizes register freeing at all estimated pressure
levels. SH1 retains that order at higher estimated pressure, while restoring
upstream max-delay and nearest-consumer tie-breaks below the threshold. The
register-pressure signal is the existing per-block estimate, not measured
hardware occupancy. Texture flight window stays at V38 default 4.

## Controls

- TU_FRANE_SHADER_MODE=1: SH1 (default).
- TU_FRANE_SHADER_MODE=0: V38 instruction-order policy.
- TU_FRANE_SHADER_PRESSURE=35: threshold (default); clamped to 20..80.

Mode and normalized threshold enter both Vulkan and IR3 shader cache keys.
Restart the container when changing variables. Each mode needs its own warm-up.
Other V38 settings remain as in the base; new code touches only IR3 ordering,
compiler option initialization, cache identities and display name.

## Validation and comparison

Host policy boundary tests, existing V38 checks, real IR3 shader compilation
with NIR/IR3 validation in a debugoptimized build, and Android cross-compilation
are required by the workflow. The synthetic corpus covers compute loads, texture
fragment shaders, varying live ranges, ALU/SFU dependencies and divergent branches.
Repeated mode-0 compilation must be binary-identical; SH1 must change at least
one shader binary. Compilation tests do not establish GPU correctness or speed.

On A810 compare original V38 and SH1 with the same resolution, DXVK, FEX, game
settings and similar starting temperature. Use three Crysis passes, then another
game such as Dirt 3. Record averages, visible fluidity and rendering artifacts.
No FPS gain is claimed before device testing. This is an experiment, not a public
release or a replacement for S2.1.
