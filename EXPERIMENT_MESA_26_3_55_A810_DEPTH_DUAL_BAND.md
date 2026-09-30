# Drnas Turnip V55 DEPTH-DUAL-BAND

V54 is preserved unchanged as the reference base.

Observed V54 default (16..31), 3-pass Crysis TimeDemo:

- Run 0: 31.12 FPS
- Run 1: 33.62 FPS
- Run 2: 33.37 FPS
- Min: 20.64 FPS
- Max: 44.36 FPS

V53's narrower 16..23 window had a slightly stronger warm result and minimum,
so V55 does **not** keep blindly widening through 24..31.

Instead, V55 keeps the known-good primary band **16..23**, skips **24..31**,
and enables a second isolated probe band **32..39** by default.

That gives us one clean question: is there another profitable depth-only GMEM
island above the weak 24..31 region?

Run V55 with **no extra environment variables** and the same 3-pass Crysis
TimeDemo.

Default controls are already active:

- `TU_FRANE_DEPTH_DRAWS=16`
- `TU_FRANE_DEPTH_MAX=23`
- `TU_FRANE_DEPTH_BAND2_MIN=32`
- `TU_FRANE_DEPTH_BAND2_MAX=39`

For exact fallback/A-B, `TU_FRANE_DEPTH_BAND2_MIN=0` disables only the new
second band.
