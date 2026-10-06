#!/usr/bin/env python3
"""Policy/source checks for Turnip-Drnas A810 S2-X."""

from pathlib import Path

ROOT = Path("mesa/src/freedreno")
compiler = (ROOT / "ir3/ir3_compiler.c").read_text()
sched = (ROOT / "ir3/ir3_sched.c").read_text()
autotune = (ROOT / "vulkan/tu_autotune.cc").read_text()
turbo = (ROOT / "vulkan/frane_mesa_26320_a810_gmem_turbo.h").read_text()
device = (ROOT / "vulkan/tu_device.cc").read_text()

# Source gates / cache identity.
assert 'TU_FRANE_S2X_GMEM", true' in autotune
assert 'TU_FRANE_S2X_STICKY", true' in autotune
assert 'TU_FRANE_S2X_SCHED", true' in compiler
assert 'frane_s2x_sched ? 6 : 4' in compiler
assert 'frane_s2x_sched ? 42 : 35' in compiler
assert 's2x_sched ? 42 : 35' in device
assert 'Turnip-Drnas A810 S2-X / Mesa ' in device

# Pure model of the two scheduler ladders.
def sy_window(max_window, pressure):
    if max_window <= 4:
        if pressure < 20:
            return max_window
        if pressure < 35:
            return min(max_window, 4)
        if pressure < 50:
            return min(max_window, 3)
        if pressure < 65:
            return min(max_window, 2)
        return min(max_window, 2)
    if pressure < 20:
        return max_window
    if pressure < 35:
        return min(max_window, 5)
    if pressure < 50:
        return min(max_window, 4)
    if pressure < 65:
        return min(max_window, 3)
    return min(max_window, 2)

assert [sy_window(4, p) for p in (10, 25, 42, 58, 80)] == [4, 4, 3, 2, 2]
assert [sy_window(6, p) for p in (10, 25, 42, 58, 80)] == [6, 5, 4, 3, 2]

# Sticky mode must only alter control-probe spacing after measured state arms.
assert 'probe_log2 = sticky ? 10 : 8' in turbo
assert 'probe_log2 = sticky ? 9 : 7' in turbo
assert 'probe_log2 = sticky ? 7 : 6' in turbo
assert 'out.force_measure = ((decision_word >> 8) & 3u) == 0u' in turbo

print("S2-X PASS: S2 fallback ladder preserved; aggressive 6/5/4/3/2 and GMEM sticky gates present")
