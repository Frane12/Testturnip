#!/usr/bin/env python3
"""Drnas Turnip V53 DEPTH-WINDOW.

Layered strictly on the successful V52 CLEAN-INTERFACE build.

Field result:
- Crysis with TU_FRANE_DEPTH_DRAWS=16 was slightly better than 24.
- That directly tells us the passes in the 16..23 draw band are useful.
- What we still do not know is whether passes above 23 are also helping.

V53 isolates that band with one new short control:

  TU_FRANE_DEPTH_DRAWS=16   minimum draw count (default)
  TU_FRANE_DEPTH_MAX=23     maximum draw count, inclusive (default)
  TU_FRANE_DEPTH_MAX=0      disable the upper cap, reproducing V52 >=min logic

So the V53 default only overrides safe depth-only PROFILED SYSMEM passes into
GMEM when drawcall_count is in [16, 23].

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
            f"V53 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V53 PASS {label}", flush=True)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   static const uint32_t min_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_DRAWS", 0),
         INT64_C(0), INT64_C(4096)));

   if (mode == 1 && drawcall_count < min_draws)
      return current;
""",
    """   static const uint32_t min_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_DRAWS", 16),
         INT64_C(0), INT64_C(4096)));

   /* V53: isolate the 16..23 band exposed by the V52 16-vs-24 A/B.
    * max_draws=0 restores the exact V52 >=min behavior.
    */
   static const uint32_t max_draws =
      static_cast<uint32_t>(std::clamp<int64_t>(
         debug_get_num_option("TU_FRANE_DEPTH_MAX", 23),
         INT64_C(0), INT64_C(4096)));

   if (mode == 1 &&
       (drawcall_count < min_draws ||
        (max_draws != 0 && drawcall_count > max_draws)))
      return current;
""",
    "isolate depth override to a bounded draw window",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V52 / Mesa ",
    "Drnas Turnip V53 / Mesa ",
    "V53 display identity",
)

a = (V / "tu_autotune.cc").read_text()
d = (V / "tu_device.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()
cmd = (V / "tu_cmd_buffer.cc").read_text()

for needle in (
    'TU_FRANE_DEPTH_MODE',
    'TU_FRANE_DEPTH_DRAWS", 16',
    'TU_FRANE_DEPTH_MAX", 23',
    "drawcall_count < min_draws",
    "max_draws != 0 && drawcall_count > max_draws",
):
    assert needle in a, needle

# V52 clean namespace and validated policies stay intact.
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
assert "Drnas Turnip V53 / Mesa " in d

print("Drnas Turnip V53 DEPTH-WINDOW applied", flush=True)
