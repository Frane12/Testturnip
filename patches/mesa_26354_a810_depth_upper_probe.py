#!/usr/bin/env python3
"""Drnas Turnip V54 UPPER-PROBE.

Layered strictly on the successful V53 DEPTH-WINDOW build.

Field result from V53:
- default 16..23 depth-only window held the warm Crysis average at ~33.70 FPS
- minimum rose to 21.71 FPS
- unbounded >=16 was already shown to be worse

V54 keeps the known-good lower frontier at 16 and moves only the upper
frontier from 23 to 31. This tests the next isolated band, 24..31, without
re-admitting the very heavy tail.

Controls remain short and unchanged:
  TU_FRANE_DEPTH_DRAWS=16
  TU_FRANE_DEPTH_MAX=31
  TU_FRANE_DEPTH_MODE=1

No GMEM packing/layout, LRZ, CB, MSAA/resolve, barriers, shaders, attachment
load/store programming or correctness gates are changed.
"""
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V54 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V54 PASS {label}", flush=True)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    'debug_get_num_option("TU_FRANE_DEPTH_MAX", 23)',
    'debug_get_num_option("TU_FRANE_DEPTH_MAX", 31)',
    "raise depth-window upper frontier 23 -> 31",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V53 / Mesa ",
    "Drnas Turnip V54 / Mesa ",
    "V54 display identity",
)

a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_DEPTH_MODE',
    'TU_FRANE_DEPTH_DRAWS", 16',
    'TU_FRANE_DEPTH_MAX", 31',
    "drawcall_count < min_draws",
    "max_draws != 0 && drawcall_count > max_draws",
):
    assert needle in a, needle

for needle in (
    "TU_FRANE_GMEM_SAFE",
    "TU_FRANE_SIMPLE_DEPTH",
    "TU_FRANE_SIMPLE_DS",
    "TU_FRANE_PACKED_DS",
    "TU_FRANE_STENCIL_LS",
):
    assert needle in a, needle

assert "TU_FRANE_GMEM_PRESSURE" in passcc
assert "TU_FRANE_CB_MODE" in cmd
assert "Drnas Turnip V54 / Mesa " in d

print("Drnas Turnip V54 UPPER-PROBE applied", flush=True)
