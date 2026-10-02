#!/usr/bin/env python3
"""Drnas Turnip V58 A810 LRZ-KEEP.

Base: V57X EDGE-STRETCH, with the proven hard-tail-only EDGE=1 default.

This experiment leaves the shader scheduler untouched (legacy V57X behavior)
and changes one LRZ validity decision on A8XX:

If a fragment shader forces LRZ off for the current draw but depth writes are
disabled, keep the LRZ buffer valid and only disable LRZ temporarily for that
draw. No depth write means the LRZ contents cannot be changed by that draw, so
later compatible draws may safely use LRZ again.

The old conservative invalidation remains for the risky case:
A8XX + GPU direction tracking + unknown previous direction + actual depth write.
"""
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V58 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V58 PASS {label}", flush=True)

# Lock the no-variable baseline to the V57X hard-tail result we already kept.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    'debug_get_num_option("TU_FRANE_EDGE", 2)',
    'debug_get_num_option("TU_FRANE_EDGE", 1)',
    "make EDGE=1 the V58 default",
)

# Safe LRZ retention:
# The current draw still has LRZ disabled exactly as before.  The only change is
# that on A8XX we do not permanently invalidate the LRZ buffer when this draw
# cannot write depth.  This follows the invariant already documented directly
# below this block in tu_lrz.cc: if Z is not written, it does not affect LRZ
# buffer state.
edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """   if (disable_lrz_due_to_fs) {
      if (cmd->state.lrz.prev_direction != TU_LRZ_UNKNOWN || !cmd->state.lrz.gpu_dir_tracking) {
         perf_debug(cmd->device, "Skipping LRZ due to FS");
         temporary_disable_lrz = true;
      } else {
         tu_lrz_invalidate(cmd, "FS writes depth or has side-effects (TODO: fix for gpu-direction-tracking case)");
      }
   }
""",
    """   if (disable_lrz_due_to_fs) {
      /*
       * V58 A810/A8XX LRZ-KEEP:
       * If this draw cannot write depth, it cannot damage the LRZ contents.
       * Keep the buffer valid and only skip LRZ for this draw, allowing later
       * compatible draws to resume LRZ.  Preserve the old conservative
       * invalidation for an actual depth-writing draw with unknown direction.
       */
      if ((CHIP >= A8XX && !z_write_enable) ||
          cmd->state.lrz.prev_direction != TU_LRZ_UNKNOWN ||
          !cmd->state.lrz.gpu_dir_tracking) {
         perf_debug(cmd->device, "Skipping LRZ due to FS");
         temporary_disable_lrz = true;
      } else {
         tu_lrz_invalidate(cmd, "FS writes depth or has side-effects (TODO: fix for gpu-direction-tracking case)");
      }
   }
""",
    "retain LRZ validity for A8XX no-depth-write FS hazards",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V57X / Mesa ",
    "Drnas Turnip V58 / Mesa ",
    "V58 display identity",
)

lrz = (V / "tu_lrz.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
device = (V / "tu_device.cc").read_text()

assert "V58 A810/A8XX LRZ-KEEP" in lrz
assert "(CHIP >= A8XX && !z_write_enable)" in lrz
assert 'debug_get_num_option("TU_FRANE_EDGE", 1)' in autotune
assert 'TU_FRANE_TAIL", true' in autotune
assert 'TU_FRANE_GMEM_TURBO", true' in autotune
assert 'TU_FRANE_DEPTH_DRAWS", 16' in autotune
assert 'TU_FRANE_DEPTH_MAX", 23' in autotune
assert "Drnas Turnip V58 / Mesa " in device

print("Drnas Turnip V58 LRZ-KEEP applied", flush=True)
