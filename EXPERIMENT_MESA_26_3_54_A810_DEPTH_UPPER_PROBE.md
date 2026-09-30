# Drnas Turnip V54 UPPER-PROBE

V54 starts exactly from the successful V53 DEPTH-WINDOW result.

Observed V53 default (16..23) in the 3-pass Crysis TimeDemo:

- Run 0: 31.38 FPS
- Run 1: 33.69 FPS
- Run 2: 33.71 FPS
- Min: 21.71 FPS

The lower frontier stays fixed at 16. V54 changes only the upper frontier:

- V53: `TU_FRANE_DEPTH_MAX=23`
- V54: `TU_FRANE_DEPTH_MAX=31`

So the default V54 window is **16..31**. The experiment asks one clean
question: does adding the 24..31 depth-only band help, or does the useful
region really end close to 23?

Run V54 with **no extra variables** and the same 3-pass Crysis TimeDemo.

Interpretation:

- If V54 beats V53, the useful region extends above 23 and the next probe can
  move the upper frontier farther out.
- If V54 loses to V53, the cutoff is inside 24..31 and the next probe should
  tighten to about 27.
- If the average is flat but the minimum changes, use the minimum/frametime
  behavior to decide which side of the boundary is healthier.

All other V53 logic and the short `TU_FRANE_*` namespace remain unchanged.
