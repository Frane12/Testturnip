#!/usr/bin/env python3
"""Model/source invariants for 26.3.36 TURBO-HUNT."""

from pathlib import Path

def v35_window(max_window, p):
    if p < 20:
        return max_window
    if p < 35:
        return min(max_window, 4)
    if p < 50:
        return min(max_window, 3)
    if p < 65:
        return min(max_window, 2)
    return min(max_window, 2)

# V36 only changes the default max from 4 to 3.
assert [v35_window(4, p) for p in (0, 25, 40, 55, 80)] == [4, 4, 3, 2, 2]
assert [v35_window(3, p) for p in (0, 25, 40, 55, 80)] == [3, 3, 3, 2, 2]
assert [v35_window(2, p) for p in (0, 25, 40, 55, 80)] == [2, 2, 2, 2, 2]

root = Path("mesa/src/freedreno")
compiler = (root / "ir3/ir3_compiler.c").read_text()
sched = (root / "ir3/ir3_sched.c").read_text()
device = (root / "vulkan/tu_device.cc").read_text()
autotune = (root / "vulkan/tu_autotune.cc").read_text()
lower = (root / "ir3/ir3_nir_lower_tex_prefetch.c").read_text()
tu_pass = (root / "vulkan/tu_pass.cc").read_text()

assert 'TU_A810_26317_TEX_WINDOW_MAX", 3' in compiler
assert 'TU_A810_26316_PREFETCH_USE_SCORE", true' in compiler
assert 'TU_A810_26320_GMEM_TURBO", true' in autotune
assert 'TU_A810_26317_TEX_WINDOW_MAX", 3' in device
assert 'TU_A810_26316_PREFETCH_USE_SCORE", true' in device

# Exact V35 A/B values remain accepted.
assert 'MIN2(8u, MAX2(2u, frane_tex_window))' in compiler
assert 'MIN2(8u, MAX2(2u, window))' in device

# Existing guards remain.
assert 'ok_tex_samp(tex, allow_bindless)' in lower
assert 'uses > best_uses' in lower
assert 'candidate_pixels > pixels' in tu_pass
assert 'frane_lifetime_candidate_can_beat' in tu_pass
assert 'return MIN2(max_window, 4u);' in sched
assert 'return MIN2(max_window, 3u);' in sched

print("26.3.36 TURBO-HUNT source/model PASS")
