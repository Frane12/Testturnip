#!/usr/bin/env python3
"""A830 S2-BW1: bandwidth/tile-memory prior over S2-D2.

Runs after:
  patches/a830-smart2-complete.patch
  patches/a830_upstream_rebase.py
  patches/a830_s2_d2.py

Key goals:
  * let the A830 runtime accept its real multi-MiB GMEM instead of the old
    A810-era 2 MiB sanity ceiling;
  * use selected tile occupancy + Mesa attachment bandwidth estimates as an
    A830-only prior;
  * preserve S2-D2 GMEM bounds, measured PROFILED history, tail learner,
    allocator authority and all synchronization/register programming.

A/B:
  TU_FRANE_A830_BW1=1  default
  TU_FRANE_A830_BW1=0  disables only the BW1 score contribution.
"""

from pathlib import Path
import hashlib
import shutil

ROOT = Path("mesa/src/freedreno")
V = ROOT / "vulkan"

before = {
    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ROOT.rglob("*") if p.is_file()
}

def edit(path: Path, old: str, new: str, label: str) -> None:
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"S2-BW1 source drift {label}: expected one anchor, saw {n}: {old[:180]!r}"
        )
    path.write_text(s.replace(old, new, 1))
    print(f"S2-BW1 PASS {label}", flush=True)

shutil.copyfile("patches/frane_a830_s2_bw1.h", V / "frane_a830_s2_bw1.h")

# The old helper was born on A810 and rejected physical GMEM above 2 MiB.
# A830 is exact-device gated by the caller, so widen only the sanity envelope;
# the real allocator-reported physical/usable values remain authoritative.
runtime = V / "frane_mesa_2634_a810_gmem_runtime.h"
edit(
    runtime,
    "   constexpr uint64_t MAX_ESTIMATED_TILES = 24ull;",
    "   constexpr uint64_t MAX_ESTIMATED_TILES = 24ull;\n"
    "   constexpr uint64_t MAX_PHYSICAL_GMEM = 16ull * 1024ull * KiB;",
    "add A830 GMEM sanity envelope",
)
edit(
    runtime,
    "      in.physical_gmem <= 2048ull * KiB &&",
    "      in.physical_gmem <= MAX_PHYSICAL_GMEM &&",
    "accept multi-MiB A830 physical GMEM",
)

smart = V / "frane_mesa_26318_a810_smart_gmem.h"
edit(
    smart,
    '#include "frane_a830_s2d2_gmem.h"',
    '#include "frane_a830_s2d2_gmem.h"\n'
    '#include "frane_a830_s2_bw1.h"',
    "include BW1 policy",
)
edit(
    smart,
    """   uint32_t peak_live_cpp = 0;
   uint32_t peak_live_planes = 0;
};""",
    """   uint32_t peak_live_cpp = 0;
   uint32_t peak_live_planes = 0;
   bool a830_bw1 = false;
};""",
    "add exact-A830 BW1 input gate",
)
edit(
    smart,
    """   if (s2d2.valid)
      score += s2d2.score_bonus;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    """   if (s2d2.valid)
      score += s2d2.score_bonus;

   if (in.a830_bw1) {
      const auto bw1 = frane_a830_s2bw1_evaluate(
         in.layout.pass_pixels,
         in.selected_tile_pixels,
         in.allocator_capacity_pixels,
         in.layout.drawcalls,
         in.sysmem_bandwidth_per_pixel,
         in.gmem_bandwidth_per_pixel,
         in.peak_live_cpp,
         uint32_t(std::min<uint64_t>(in.layout.usable_gmem, UINT32_MAX)),
         in.peak_live_planes);
      if (bw1.valid)
         score += bw1.score_delta;
   }

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    "blend A830 bandwidth/tile prior",
)

auto = V / "tu_autotune.cc"
edit(
    auto,
    """static bool
frane_a830_s2d2_footprint_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_FOOTPRINT", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
    """static bool
frane_a830_s2d2_footprint_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_FOOTPRINT", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_s2bw1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW1", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
    "add BW1 runtime gate",
)
edit(
    auto,
    """         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;""",
    """         runtime_input.a830_bw1 =
            frane_a830_s2bw1_enabled(device);

         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;""",
    "feed BW1 exact-device gate",
)

edit(
    V / "tu_device.cc",
    "Turnip-Drnas A830 S2-D2 / Mesa ",
    "Turnip-Drnas A830 S2-BW1 / Mesa ",
    "S2-BW1 driver identity",
)

# Integration checks.
runtime_text = runtime.read_text()
smart_text = smart.read_text()
auto_text = auto.read_text()
device_text = (V / "tu_device.cc").read_text()

for needle in (
    "MAX_PHYSICAL_GMEM = 16ull * 1024ull * KiB",
    "in.physical_gmem <= MAX_PHYSICAL_GMEM",
):
    assert needle in runtime_text, needle

for needle in (
    '#include "frane_a830_s2_bw1.h"',
    "bool a830_bw1 = false",
    "frane_a830_s2bw1_evaluate",
):
    assert needle in smart_text, needle

for needle in (
    'TU_FRANE_A830_BW1", true',
    "runtime_input.a830_bw1",
    'TU_FRANE_A830_FOOTPRINT", true',
):
    assert needle in auto_text, needle

assert "Turnip-Drnas A830 S2-BW1 / Mesa " in device_text

after = {
    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ROOT.rglob("*") if p.is_file()
}
changed = {k for k in before.keys() | after.keys()
           if before.get(k) != after.get(k)}
expected = {
    "vulkan/frane_a830_s2_bw1.h",
    "vulkan/frane_mesa_2634_a810_gmem_runtime.h",
    "vulkan/frane_mesa_26318_a810_smart_gmem.h",
    "vulkan/tu_autotune.cc",
    "vulkan/tu_device.cc",
}
if changed != expected:
    raise SystemExit(f"S2-BW1 unexpected source scope: {sorted(changed ^ expected)}")

print("A830 S2-BW1 applied; source scope verified", flush=True)
