#!/usr/bin/env python3
"""Pin Mesa 26.2.3 and port Frane V19 adaptive A810 over the V18 base."""
import sys
import runpy
from pathlib import Path

if len(sys.argv) != 2 or sys.argv[1] not in ("a830", "a810"):
    raise SystemExit("Usage: port_mesa_2623.py a830|a810")

mode=sys.argv[1]
sys.argv = ["patches/port_upstream_main.py", mode]
runpy.run_path("patches/port_upstream_main.py", run_name="__main__")

if mode == "a810":
    runpy.run_path("patches/v17_a810_light_burst.py", run_name="__main__")
    # V17 lighting/burst experiments had no confirmed flicker fix:
    # retain both but default them OFF to isolate DiskDVD shader workaround.
    p = Path("mesa/src/freedreno/vulkan/tu_image.cc")
    s = p.read_text()
    a = 'const char *env = os_get_option("TU_A810_SAFE_DEPTH_UBWC");\n      return !env || strcmp(env, "0") != 0;'
    assert s.count(a)==1
    p.write_text(s.replace(a,'const char *env = os_get_option("TU_A810_SAFE_DEPTH_UBWC");\n      return env && strcmp(env, "1") == 0;',1))
    p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
    s = p.read_text()
    a = 'const char *env = os_get_option("TU_A810_GMEM_BURST");\n                  return !env || strcmp(env, "0") != 0;'
    assert s.count(a)==1
    p.write_text(s.replace(a,'const char *env = os_get_option("TU_A810_GMEM_BURST");\n                  return env && strcmp(env, "1") == 0;',1))
    runpy.run_path("patches/diskdvd_a810_ir3_prefetch.py", run_name="__main__")
    runpy.run_path("patches/v18_a810_sampled_depth.py", run_name="__main__")
    runpy.run_path("patches/v19_a810_adaptive_autotune.py", run_name="__main__")
else:
    print("A830: retain V16, do not port A810-specific DiskDVD shader workarounds",flush=True)

p=Path("mesa/src/freedreno/vulkan/tu_device.cc")
s=p.read_text()
a="Frane V17 A810 LIGHT-BURST / Mesa " if mode=="a810" else "Frane V16 A830 UPSTREAM / Mesa "
b="Frane A810 V19-ADAPTIVE-AUTOTUNE / Mesa " if mode=="a810" else "Frane A830 V16-DISKDVD-AUDIT / Mesa "
assert s.count(a)==1
p.write_text(s.replace(a,b,1))
print(f"ALL Mesa 26.2.3 {mode} patches ported",flush=True)
