# Drnas Turnip V53 DEPTH-WINDOW

This build starts from the successful V52 CLEAN-INTERFACE build.

The Crysis A/B showed that a 16-draw minimum is slightly better than a 24-draw
minimum. That means the 16..23 draw band is doing useful work. V53 asks the next
clean question: do we actually need to force the heavier passes above 23 too?

Default V53 values:

- `TU_FRANE_DEPTH_DRAWS=16`
- `TU_FRANE_DEPTH_MAX=23`
- `TU_FRANE_DEPTH_MODE=1`

With no extra variables, only safe depth-only passes in the inclusive 16..23
draw band are forced from PROFILED SYSMEM to GMEM.

For the exact V52-style control path, set:

`TU_FRANE_DEPTH_MAX=0`

That removes the upper cap and returns to `draws >= minimum`.

Run the same 3-pass Crysis TimeDemo. If V53 default matches or beats V52/16,
then the useful gain is concentrated in the mid-density band and the very heavy
passes can be left to PROFILED. If it loses, passes above 23 are helping too.
