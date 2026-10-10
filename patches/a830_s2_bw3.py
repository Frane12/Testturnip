#!/usr/bin/env python3
"""A830 S2-BW3: extremely small, measured-history-confirmed GMEM prior over
the reproducible S2-BW2 Tile Cost, with exact opt-out.
Apply after patches/a830_s2_bw2.py.
No new profiler, no separate GMEM selector, no IR3/WSI/GMEM layout changes.
"""
from pathlib import Path
import hashlib, shutil

ROOT=Path("mesa/src/freedreno")
V=ROOT/"vulkan"
before={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*") if p.is_file()}

def edit(path, old, new, name):
    txt=path.read_text()
    count=txt.count(old)
    if count != 1:
        raise SystemExit(f"BW3 collision/source-drift {name}: expected once; got {count}")
    path.write_text(txt.replace(old,new,1))
    print(f"BW3 PASS {name}",flush=True)

shutil.copyfile("patches/frane_a830_s2_bw3.h", V/"frane_a830_s2_bw3.h")
smart=V/"frane_mesa_26318_a810_smart_gmem.h"
edit(smart,
     '#include "frane_a830_s2_bw2.h"',
     '#include "frane_a830_s2_bw2.h"\n#include "frane_a830_s2_bw3.h"',
     "BW3 include after BW2")
edit(smart,
     "   bool a830_bw2 = false;",
     "   bool a830_bw2 = false;\n   bool a830_bw3 = false;",
     "A830-only score gate")

edit(smart,
     """      if (bw2.valid)
         score += bw2.score_delta;
   }

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
     """      if (bw2.valid) {
         score += bw2.score_delta;
         if (in.a830_bw3) {
            const auto bw3 = frane_a830_s2bw3_adjust(
               bw2, in.layout.drawcalls,
               in.sysmem_bandwidth_per_pixel,
               in.gmem_bandwidth_per_pixel,
               in.a830_history_score,
               in.a830_history_pairs,
               in.a830_history_ready);
            if (bw3.valid)
               score += bw3.score_delta;
         }
      }
   }

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
     "BW3 bounded correction inside existing BW2 score")

auto=V/"tu_autotune.cc"
edit(auto,
     """static bool
frane_a830_s2bw2_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW2", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     """static bool
frane_a830_s2bw2_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW2", true);
   return enabled && frane_26320_a830_gpu(device);
}

static bool
frane_a830_s2bw3_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_A830_BW3", true);
   return enabled && frane_26320_a830_gpu(device);
}
""",
     "exact-device A830 switch, independent rollback")
edit(auto,
     """         runtime_input.a830_bw2 =
            frane_a830_s2bw2_enabled(device);

         if (runtime_input.a830_bw2) {""",
     """         runtime_input.a830_bw2 =
            frane_a830_s2bw2_enabled(device);
         runtime_input.a830_bw3 =
            runtime_input.a830_bw2 && frane_a830_s2bw3_enabled(device);

         if (runtime_input.a830_bw2) {""",
     "gate BW3 behind BW2 and exact A830")

edit(V/"tu_device.cc",
     "Turnip-Drnas A830 S2-BW2 Adaptive Tile Cost / Mesa ",
     "Turnip-Drnas A830 S2-BW3 Tile Cost Lite / Mesa ",
     "driver identity")
t=smart.read_text();a=auto.read_text();d=(V/"tu_device.cc").read_text()
assert '#include "frane_a830_s2_bw3.h"' in t
assert "frane_a830_s2bw3_adjust(" in t
assert 'TU_FRANE_A830_BW3", true' in a
assert "runtime_input.a830_bw2 && frane_a830_s2bw3_enabled(device)" in a
assert "Turnip-Drnas A830 S2-BW3 Tile Cost Lite / Mesa " in d
after={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
       for p in ROOT.rglob("*") if p.is_file()}
changed={k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)}
expected={
   "vulkan/frane_a830_s2_bw3.h",
   "vulkan/frane_mesa_26318_a810_smart_gmem.h",
   "vulkan/tu_autotune.cc",
   "vulkan/tu_device.cc",
}
if changed!=expected:
    raise SystemExit(f"BW3 unexpected source scope {sorted(changed ^ expected)}")
print("A830 BW3 runtime integration and source scope verified",flush=True)
