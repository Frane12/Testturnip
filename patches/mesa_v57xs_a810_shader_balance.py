#!/usr/bin/env python3
"""Drnas Turnip V57XS A810 SHADER-BALANCE.

Base: V57X EDGE-STRETCH, but with the tested hard-tail-only mode (EDGE=1)
made the default. The only new performance surface is a pressure-balanced
IR3 SY/texture scheduling window.

TU_FRANE_SHADER=1 -> pressure-balanced shader scheduler (default)
TU_FRANE_SHADER=0 -> exact legacy V57X/V25 scheduler
TU_FRANE_EDGE=0/1/2 remains available; default is changed from 2 to 1.

The shader toggle is included in both Vulkan and IR3 disk-cache identities.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
F = ROOT / "src/freedreno"
V = F / "vulkan"
I = F / "ir3"

def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"V57XS source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V57XS PASS {label}", flush=True)

def add_include(path, inc):
    p = ROOT / path
    s = p.read_text()
    line = f'#include "{inc}"'
    if line in s:
        return
    rows = s.splitlines()
    last = -1
    for idx, row in enumerate(rows[:120]):
        if row.startswith("#include "):
            last = idx
    if last < 0:
        raise SystemExit(f"V57XS source drift: no include block in {path}")
    rows.insert(last + 1, line)
    p.write_text("\n".join(rows) + ("\n" if s.endswith("\n") else ""))
    print(f"V57XS PASS include {inc} in {path}", flush=True)

shutil.copyfile(
    "patches/frane_v57xs_a810_shader_balance.h",
    I / "frane_v57xs_a810_shader_balance.h",
)

# Lock the new no-variable baseline to the hardware result that survived
# both Dirt 3 and the Crysis crash check: V57X hard-tail-only.
edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    'debug_get_num_option("TU_FRANE_EDGE", 2)',
    'debug_get_num_option("TU_FRANE_EDGE", 1)',
    "make EDGE=1 the V57XS default",
)

# ---------------------------------------------------------------------------
# SHADER-BALANCE
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;
""",
    """   bool frane_26317_adaptive_sched;
   uint8_t frane_26317_tex_window_max;

   /* V57XS broad-workload scheduler controller. */
   bool frane_v57xs_shader_balance;
""",
    "add V57XS compiler policy bit",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26317_adaptive_sched =
         debug_get_bool_option("TU_A810_26317_ADAPTIVE_SCHED", true);

      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(2u, frane_tex_window));
""",
    """      compiler->frane_26317_adaptive_sched =
         debug_get_bool_option("TU_A810_26317_ADAPTIVE_SCHED", true);

      unsigned frane_tex_window =
         debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4);
      compiler->frane_26317_tex_window_max =
         MIN2(8u, MAX2(2u, frane_tex_window));

      compiler->frane_v57xs_shader_balance =
         debug_get_bool_option("TU_FRANE_SHADER", true);
""",
    "enable V57XS shader balance by default",
)

add_include(
    "src/freedreno/ir3/ir3_sched.c",
    "frane_v57xs_a810_shader_balance.h",
)

edit(
    "src/freedreno/ir3/ir3_sched.c",
    """   /* 26.3.25 A810 hardware-guided ladder.
    * The default max=4 path is 4/4/3/2/2.  Larger env overrides are kept only
    * for A/B comparison; pressure rapidly pulls them back toward short live
    * ranges.  The adaptive opt-out remains upstream fixed sy=8.
    */
   if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 4u);
   if (p < 50)
      return MIN2(max_window, 3u);
   if (p < 65)
      return MIN2(max_window, 2u);
   return MIN2(max_window, 2u);""",
    """   /* Exact V57X/V25 behavior remains available when TU_FRANE_SHADER=0. */
   unsigned legacy_window;
   if (p < 20)
      legacy_window = max_window;
   else if (p < 35)
      legacy_window = MIN2(max_window, 4u);
   else if (p < 50)
      legacy_window = MIN2(max_window, 3u);
   else
      legacy_window = MIN2(max_window, 2u);

   return frane_v57xs_shader_window(
      ctx->compiler->frane_v57xs_shader_balance,
      p, legacy_window);""",
    "replace fixed A810 ladder with pressure-balanced window",
)

# Vulkan cache identity: the shader policy must not silently reuse binaries
# compiled with the control path.
edit(
    "src/freedreno/vulkan/tu_device.cc",
    "frane_26323_a810_cache_options(uint32_t options[10])",
    "frane_26323_a810_cache_options(uint32_t options[11])",
    "extend Vulkan compiler-option cache vector",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    """   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
}""",
    """   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
   options[10] = debug_get_bool_option("TU_FRANE_SHADER", true);
}""",
    "hash V57XS shader policy in Vulkan cache identity",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "      uint32_t options[10];",
    "      uint32_t options[11];",
    "resize Vulkan compiler-option cache vector",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    'static const char schema[] = "frane-a810-compile-options-v1";',
    'static const char schema[] = "frane-a810-compile-options-v2";',
    "bump Vulkan A810 compiler cache schema",
)

# IR3 disk-cache identity: append the resolved bool.
edit(
    "src/freedreno/ir3/ir3_disk_cache.c",
    """         compiler->frane_26317_adaptive_sched,
         compiler->frane_26317_tex_window_max,
      };
      static const char schema[] = "frane-a810-compile-options-v1";""",
    """         compiler->frane_26317_adaptive_sched,
         compiler->frane_26317_tex_window_max,
         compiler->frane_v57xs_shader_balance,
      };
      static const char schema[] = "frane-a810-compile-options-v2";""",
    "hash V57XS shader policy in IR3 disk-cache identity",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V57X / Mesa ",
    "Drnas Turnip V57XS / Mesa ",
    "V57XS display identity",
)

# ---------------------------------------------------------------------------
# Audit guards
# ---------------------------------------------------------------------------
compiler_c = (I / "ir3_compiler.c").read_text()
compiler_h = (I / "ir3_compiler.h").read_text()
sched = (I / "ir3_sched.c").read_text()
disk = (I / "ir3_disk_cache.c").read_text()
device = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()

assert 'TU_FRANE_SHADER", true' in compiler_c
assert "frane_v57xs_shader_balance" in compiler_h
assert "frane_v57xs_shader_window" in sched
assert "legacy_window" in sched
assert "frane-a810-compile-options-v2" in device
assert "frane-a810-compile-options-v2" in disk
assert "options[10] = debug_get_bool_option" in device
assert "compiler->frane_v57xs_shader_balance" in disk
assert 'debug_get_num_option("TU_FRANE_EDGE", 1)' in autotune

# Preserve the proven V57X / V57 runtime stack.
assert 'TU_FRANE_TAIL", true' in autotune
assert 'TU_FRANE_GMEM_TURBO", true' in autotune
assert 'TU_FRANE_DEPTH_DRAWS", 16' in autotune
assert 'TU_FRANE_DEPTH_MAX", 23' in autotune
assert "frane_v57x_eval_edge" in (V / "frane_mesa_26320_a810_gmem_turbo.h").read_text()
assert "Drnas Turnip V57XS / Mesa " in device

print("Drnas Turnip V57XS SHADER-BALANCE applied", flush=True)
