#!/usr/bin/env python3
"""A830 S2-CX1: tiny A810 AT1-context prior layered on tested BW1.

Runs AFTER a830_s2_bw1.py on the pinned Mesa revision. No BW2 fast
rollback, new measurements, GMEM allocation, barriers or shader changes.
TU_FRANE_A830_CX1=0 restores exactly the BW1 policy.
"""
from pathlib import Path
import hashlib
import shutil

ROOT = Path("mesa/src/freedreno")
V = ROOT / "vulkan"
before = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in ROOT.rglob("*") if p.is_file()}

def edit(path: Path, old: str, new: str, name: str) -> None:
    s = path.read_text()
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"CX1 source drift {name}: expected 1 anchor, got {count}")
    path.write_text(s.replace(old, new, 1))
    print(f"CX1 PASS {name}", flush=True)

shutil.copyfile("patches/frane_a830_s2_cx1.h", V / "frane_a830_s2_cx1.h")
smart = V / "frane_mesa_26318_a810_smart_gmem.h"
edit(smart,
     '#include "frane_a830_s2_bw1.h"',
     '#include "frane_a830_s2_bw1.h"\n#include "frane_a830_s2_cx1.h"',
     "include CX1 helper")
edit(smart,
     "   bool a830_bw1 = false;\n};",
     "   bool a830_bw1 = false;\n   bool a830_cx1 = false;\n};",
     "carry exact A830 CX1 gate")
edit(smart,
     """      if (bw1.valid)
         score += bw1.score_delta;
   }

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
     """      if (bw1.valid) {
         score += bw1.score_delta;
         if (in.a830_cx1) {
            const auto cx1 = frane_a830_cx1_evaluate(
               bw1, in.layout.pass_pixels, in.layout.drawcalls,
               in.sysmem_bandwidth_per_pixel,
               in.gmem_bandwidth_per_pixel);
            if (cx1.valid)
               score += cx1.adjustment;
         }
      }
   }

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
     "apply conservative context correction to BW1 only")
auto = V / "tu_autotune.cc"
edit(auto,
     """static bool
frane_a830_s2bw1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW1", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     """static bool
frane_a830_s2bw1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW1", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_s2cx1_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_CX1", true);
   return enabled && frane_26320_a830_gpu(device);
}
""", "add exact A830 runtime switch")
edit(auto,
     """         runtime_input.a830_bw1 =
            frane_a830_s2bw1_enabled(device);

         runtime_input.sysmem_bandwidth_per_pixel =""",
     """         runtime_input.a830_bw1 =
            frane_a830_s2bw1_enabled(device);
         runtime_input.a830_cx1 =
            runtime_input.a830_bw1 && frane_a830_s2cx1_enabled(device);

         runtime_input.sysmem_bandwidth_per_pixel =""",
     "feed gated CX1 decision")
edit(V / "tu_device.cc",
     "Turnip-Drnas A830 S2-BW1 / Mesa ",
     "Turnip-Drnas A830 S2-CX1 / Mesa ",
     "CX1 display identity")
assert 'TU_FRANE_A830_CX1", true' in auto.read_text()
assert 'frane_a830_cx1_evaluate' in smart.read_text()
assert "Turnip-Drnas A830 S2-CX1 / Mesa " in (V / "tu_device.cc").read_text()
after = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in ROOT.rglob("*") if p.is_file()}
changed = {k for k in before.keys() | after.keys()
           if before.get(k) != after.get(k)}
expected = {
    "vulkan/frane_a830_s2_cx1.h",
    "vulkan/frane_mesa_26318_a810_smart_gmem.h",
    "vulkan/tu_autotune.cc",
    "vulkan/tu_device.cc",
}
if changed != expected:
    raise SystemExit(f"CX1 unexpected source scope: {sorted(changed ^ expected)}")
print("A830 S2-CX1 integration/scope PASS", flush=True)
