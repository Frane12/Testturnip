#!/usr/bin/env python3
"""V28-CLEAN experiment: no A810 custom GMEM runtime and no WSI override.

Apply after V28 Universal Adaptive. The V28 PROFILED learner, stable RP hash,
persistent weak prior and all unrelated correctness/power patches remain.
"""
from pathlib import Path

ROOT = Path("mesa")

def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V28-CLEAN source drift: {label}: expected 1 anchor, saw {n}: {old[:140]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"V28-CLEAN PASS {label}", flush=True)

# A810 is no longer treated as part of the older A830/A810 custom BANDWIDTH
# runtime policy. A830 behavior remains unchanged.
edit("src/freedreno/vulkan/tu_autotune.cc",
'''   return a830 ||
      (frane_a810_gpu(device) && frane_a810_gmem_profile() != 0);''',
'''   return a830;''',
"remove A810 from custom smart-GMEM runtime")

# Ignore the old A810 profile=0 rollback as an algorithm selector in this
# experiment. With no explicit TU_AUTOTUNE_ALGO, A810 continues into the
# V22/V28 PROFILED learner rather than being forced to prefer_sysmem.
edit("src/freedreno/vulkan/tu_autotune.cc",
'''      else if (frane_a810_gpu(device) && frane_a810_gmem_profile() == 0)
         /* Prefer SYSMEM for A810 by default; TU_DEBUG=sysmem strictly
          * enforces it for diagnosis. Explicit user algorithm still wins.
          */
         algo_strv = "prefer_sysmem";
      else if (frane_a810_gpu(device) && frane_a810_lean_profiled())''',
'''      else if (frane_a810_gpu(device) && frane_a810_lean_profiled())''',
"remove legacy A810 profile=0 algorithm override")

# Even if the user explicitly selects BANDWIDTH, do not pass the A810 flag
# into the custom cost model. That makes BANDWIDTH use its ordinary Mesa/A830
# path, with no A810 bounded-runtime heuristics.
edit("src/freedreno/vulkan/tu_autotune.cc",
'''         smart, smart ? frane_a830_gmem_pressure_tier() : 2u,
         frane_a810_gpu(device),
         device->physical_device->gmem_size,''',
'''         smart, smart ? frane_a830_gmem_pressure_tier() : 2u,
         false,
         device->physical_device->gmem_size,''',
"remove A810 runtime flag from bandwidth selector")

# Remove the V23 WSI override completely. The application/DXVK and upstream
# Mesa WSI decide present mode normally.
p = ROOT / "src/freedreno/vulkan/tu_wsi.cc"
s = p.read_text()
s2 = s.replace('''#include "tu_device.h"
#include "frane_present_policy.h"
#include "util/os_misc.h"
#include <stdio.h>''', '''#include "tu_device.h"''', 1)
if s2 == s:
    raise SystemExit("V28-CLEAN source drift: V23 include block not found")
s = s2

start = s.find('''   /* A810-only built-in WSI presentation experiment.''')
end_marker = '''   physical_device->wsi_device.supports_modifiers = true;'''
end = s.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("V28-CLEAN source drift: V23 WSI override block not found")
s = s[:start] + '''   /* V28-CLEAN: no driver present-mode override. Upstream WSI/client choice. */
''' + s[end:]
p.write_text(s)
print("V28-CLEAN PASS remove V23 MAILBOX/WSI override", flush=True)

edit("src/freedreno/vulkan/tu_device.cc",
     "Frane V28-UNIVERSAL-ADAPTIVE / Mesa ",
     "Frane V28-CLEAN-RUNTIME-WSI / Mesa ",
     "experiment driver identity")

print("V28-CLEAN: universal PROFILED learning retained; A810 custom GMEM runtime and forced MAILBOX removed", flush=True)
