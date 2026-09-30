#!/usr/bin/env python3
"""Drnas Turnip V55 DEPTH-DUAL-BAND.

Layered strictly on the preserved V54 UPPER-PROBE branch.

Field result from V54:
- V54 default 16..31 stayed stable, but the warm average slipped slightly
  versus V53 and the minimum moved down.
- That makes the newly admitted 24..31 band suspicious.
- Instead of simply retreating, V55 keeps the known-good 16..23 island and
  probes a separate higher island, 32..39, while leaving 24..31 alone.

Default V55 policy:
  primary band:   16..23
  secondary band: 32..39

Controls:
  TU_FRANE_DEPTH_DRAWS=16
  TU_FRANE_DEPTH_MAX=23
  TU_FRANE_DEPTH_BAND2_MIN=32
  TU_FRANE_DEPTH_BAND2_MAX=39
  TU_FRANE_DEPTH_BAND2_MIN=0 disables the second band.

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
            f"V55 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V55 PASS {label}", flush=True)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   static const uint32_t min_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_DRAWS", 16),
         INT64_C(0), INT64_C(4096)));

   /* V53: isolate the 16..23 band exposed by the V52 16-vs-24 A/B.
    * max_draws=0 restores the exact V52 >=min behavior.
    */
   static const uint32_t max_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_MAX", 31),
         INT64_C(0), INT64_C(4096)));

   if (mode == 1 &&
       (drawcall_count < min_draws ||
        (max_draws != 0 && drawcall_count > max_draws)))
      return current;
""",
    """   static const uint32_t min_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_DRAWS", 16),
         INT64_C(0), INT64_C(4096)));

   /* V55: preserve the known-good 16..23 island and jump over the V54
    * 24..31 regression candidate to probe a second isolated band.
    * max_draws=0 still restores the old >=min behavior for exact A/B.
    */
   static const uint32_t max_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_MAX", 23),
         INT64_C(0), INT64_C(4096)));
   static const uint32_t band2_min =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_BAND2_MIN", 32),
         INT64_C(0), INT64_C(4096)));
   static const uint32_t band2_max =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_BAND2_MAX", 39),
         INT64_C(0), INT64_C(4096)));

   const bool in_primary =
      drawcall_count >= min_draws &&
      (max_draws == 0 || drawcall_count <= max_draws);
   const bool in_secondary =
      band2_min != 0 && drawcall_count >= band2_min &&
      (band2_max == 0 || drawcall_count <= band2_max);

   if (mode == 1 && !in_primary && !in_secondary)
      return current;
""",
    "split depth override into known-good + high probe bands",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V54 / Mesa ",
    "Drnas Turnip V55 / Mesa ",
    "V55 display identity",
)

a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_DEPTH_MODE',
    'TU_FRANE_DEPTH_DRAWS", 16',
    'TU_FRANE_DEPTH_MAX", 23',
    'TU_FRANE_DEPTH_BAND2_MIN", 32',
    'TU_FRANE_DEPTH_BAND2_MAX", 39',
    "in_primary",
    "in_secondary",
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
assert "Drnas Turnip V55 / Mesa " in d

print("Drnas Turnip V55 DEPTH-DUAL-BAND applied", flush=True)
