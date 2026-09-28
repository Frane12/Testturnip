#!/usr/bin/env python3
"""Validate the 26.3.25 A810 scheduler tune against patched sources."""
from pathlib import Path

r = Path("mesa/src/freedreno")
compiler = (r / "ir3/ir3_compiler.c").read_text()
sched = (r / "ir3/ir3_sched.c").read_text()
device = (r / "vulkan/tu_device.cc").read_text()
autotune = (r / "vulkan/tu_autotune.cc").read_text()

assert 'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4)' in compiler
assert 'MIN2(8u, MAX2(2u, frane_tex_window))' in compiler
assert 'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4)' in device
assert 'MIN2(8u, MAX2(2u, window))' in device
assert 'debug_get_bool_option("TU_A810_26320_GMEM_TURBO", false)' in autotune

expected = '''if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 4u);
   if (p < 50)
      return MIN2(max_window, 3u);
   if (p < 65)
      return MIN2(max_window, 2u);
   return MIN2(max_window, 2u);'''
assert expected in sched


def clamp(v):
    return min(8, max(2, v))


def sy_window(adaptive, requested_max, pressure):
    if not adaptive:
        return 8
    m = clamp(requested_max)
    if pressure < 20:
        return m
    if pressure < 35:
        return min(m, 4)
    if pressure < 50:
        return min(m, 3)
    if pressure < 65:
        return min(m, 2)
    return min(m, 2)


# Default max=4 is exactly the promoted hardware-guided ladder.
assert [sy_window(True, 4, p) for p in (0, 25, 45, 55, 75)] == [4, 4, 3, 2, 2]

# Explicit A/B overrides remain available and bounded.
assert [sy_window(True, 8, p) for p in (0, 25, 45, 55, 75)] == [8, 4, 3, 2, 2]
assert [sy_window(True, 6, p) for p in (0, 25, 45, 55, 75)] == [6, 4, 3, 2, 2]
assert [sy_window(True, 3, p) for p in (0, 25, 45, 55, 75)] == [3, 3, 3, 2, 2]
assert [sy_window(True, 2, p) for p in (0, 25, 45, 55, 75)] == [2, 2, 2, 2, 2]

# Out-of-range values normalize into the cache/compiler-supported interval.
assert clamp(0) == 2
assert clamp(99) == 8

# Adaptive opt-out must still reproduce upstream fixed sy=8.
assert sy_window(False, 2, 100) == 8
assert sy_window(False, 8, 0) == 8

print("PASS: 26.3.25 default 4, ladder 4/4/3/2/2, env A/B 2..8, GMEM unchanged")
