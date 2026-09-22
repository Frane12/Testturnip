#!/usr/bin/env python3
"""Pin Mesa 26.2.3 and port Frane V16/V17 + audited DiskDVD A810 IR3 change."""
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
else:
    runpy.run_path("patches/v18_a830_depth_diagnostic.py", run_name="__main__")
    print("A830: V16 memory/GMEM retained, V18 internal depth diagnostic",flush=True)

p=Path("mesa/src/freedreno/vulkan/tu_device.cc")
s=p.read_text()
a="Frane V17 A810 LIGHT-BURST / Mesa " if mode=="a810" else "Frane V16 A830 UPSTREAM / Mesa "
b="Frane A810 V17-DISKDVD / Mesa " if mode=="a810" else "Frane A830 V18-DEPTH-DIAG / Mesa "
assert s.count(a)==1
p.write_text(s.replace(a,b,1))
print(f"ALL Mesa 26.2.3 {mode} patches ported",flush=True)
