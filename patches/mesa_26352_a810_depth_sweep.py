#!/usr/bin/env python3
"""Drnas Turnip V52 DEPTH-SWEEP.

Layered strictly on V51 DEPTH-HEAVY.

Purpose:
- Promote the field-tested 16-draw threshold to the baseline for the next sweep.
- Introduce short stable TU_FRANE_* knobs so testing on phone/tablet is practical.
- Keep legacy V50/V51 variable names as fallbacks so old presets still work.

Primary knobs:
  TU_FRANE_DEPTH_MODE=1
  TU_FRANE_DEPTH_DRAWS=16

Suggested sweep:
  16 -> 24 -> 32, then bracket the best region.

No allocator/search, LRZ, CB, MSAA/resolve, shader, barrier, packing, or
correctness-safety logic is changed.
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
            f"V52 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V52 PASS {label}", flush=True)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    'static const int mode =\n      std::clamp<int>(debug_get_num_option("TU_A810_26350_DEPTH_FRONTIER_MODE", 1), 0, 2);',
    'static const int mode =\n      std::clamp<int>(debug_get_num_option(\n         "TU_FRANE_DEPTH_MODE",\n         debug_get_num_option("TU_A810_26350_DEPTH_FRONTIER_MODE", 1)), 0, 2);',
    "add short depth-mode knob with legacy fallback",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    '''   static const uint32_t min_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_A810_26351_DEPTH_MIN_DRAWS", 0),
         INT64_C(0), INT64_C(4096)));''',
    '''   static const uint32_t min_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option(
            "TU_FRANE_DEPTH_DRAWS",
            debug_get_num_option("TU_A810_26351_DEPTH_MIN_DRAWS", 16)),
         INT64_C(0), INT64_C(4096)));''',
    "add short draw threshold knob and promote 16-draw baseline",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V51 / Mesa ",
    "Drnas Turnip V52 / Mesa ",
    "V52 display identity",
)

a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()

for needle in (
    '"TU_FRANE_DEPTH_MODE"',
    '"TU_FRANE_DEPTH_DRAWS"',
    '"TU_A810_26350_DEPTH_FRONTIER_MODE"',
    '"TU_A810_26351_DEPTH_MIN_DRAWS", 16',
    "drawcall_count < min_draws",
):
    assert needle in a, needle

assert "Drnas Turnip V52 / Mesa " in d
print("Drnas Turnip V52 DEPTH-SWEEP applied", flush=True)
