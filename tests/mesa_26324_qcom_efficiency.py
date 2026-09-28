#!/usr/bin/env python3
"""Validate the 26.3.24 A810 QCOM-efficiency policy against actual patched sources."""
from pathlib import Path
import os
import subprocess
import tempfile

r = Path("mesa/src/freedreno")
compiler = (r / "ir3/ir3_compiler.c").read_text()
sched = (r / "ir3/ir3_sched.c").read_text()
smart = (r / "vulkan/frane_mesa_26318_a810_smart_gmem.h").read_text()
autotune = (r / "vulkan/tu_autotune.cc").read_text()
device = (r / "vulkan/tu_device.cc").read_text()

assert 'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 8)' in compiler
assert 'MIN2(8u, MAX2(4u, frane_tex_window))' in compiler
assert 'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 8)' in device
assert 'MIN2(8u, MAX2(4u, window))' in device
assert 'debug_get_bool_option("TU_A810_26320_GMEM_TURBO", false)' in autotune
assert 'effective = std::max(effective, 8u);' not in smart

# Exact scheduler policy: default/max 8, optional 6/4, pressure reduction to 2.
assert '''if (p < 20)
      return max_window;
   if (p < 35)
      return MIN2(max_window, 6u);
   if (p < 50)
      return MIN2(max_window, 4u);
   if (p < 65)
      return MIN2(max_window, 4u);
   return MIN2(max_window, 2u);''' in sched

src = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include "SMART_HEADER"

static frane_26318_smart_gmem_input strong_input()
{
   frane_26318_smart_gmem_input in {};
   in.layout.physical_gmem = 576ull * 1024ull;
   in.layout.usable_gmem = 448ull * 1024ull;
   in.layout.pixels_per_tile = 131072;
   in.layout.pass_pixels = 1280ull * 720ull;
   in.layout.drawcalls = 64;
   in.sysmem_bandwidth_per_pixel = 24;
   in.gmem_bandwidth_per_pixel = 10;
   return in;
}

int main()
{
   const auto in = strong_input();
   const auto eval = frane_26318_eval_smart_gmem(in);
   assert(eval.eligible);
   assert(eval.structure_score >= 75);

   // Cold start: structure alone must not override PROFILED anymore.
   frane_2634_gmem_state cold {};
   auto d = frane_26318_decide_smart_gmem(true, in, cold, 50, 1);
   assert(!d.override_mode);
   assert(!d.force_measure);
   assert(d.structure_score == eval.structure_score);

   // Once paired timing has armed the state, SMART-GMEM can still hold GMEM.
   frane_2634_gmem_state armed {};
   armed.score = 8;
   armed.armed = true;
   d = frane_26318_decide_smart_gmem(true, in, armed, 20, 1);
   assert(d.override_mode);
   assert(!d.select_sysmem);
   assert(d.probe_log2 == 7);

   // Control probe remains measured.
   d = frane_26318_decide_smart_gmem(true, in, armed, 20, 128);
   assert(d.override_mode);
   assert(d.select_sysmem);
   assert(d.force_measure);

   std::puts("26.3.24 measured-first SMART-GMEM PASS");
   return 0;
}
'''

header = (r / "vulkan/frane_mesa_26318_a810_smart_gmem.h").resolve()
src = src.replace("SMART_HEADER", str(header))

with tempfile.TemporaryDirectory() as d:
    cpp = Path(d) / "qcom_efficiency.cpp"
    exe = Path(d) / "qcom_efficiency"
    cpp.write_text(src)
    subprocess.run(
        ["g++", "-std=c++17", "-O2", "-Wall", "-Wextra", "-Werror",
         "-fsanitize=address,undefined", str(cpp), "-o", str(exe)],
        check=True,
    )
    subprocess.run(
        [str(exe)],
        check=True,
        env={
            **os.environ,
            "ASAN_OPTIONS": os.environ.get(
                "ASAN_OPTIONS", "detect_leaks=1:halt_on_error=1"
            ),
            "UBSAN_OPTIONS": "halt_on_error=1",
        },
    )

print("PASS: scheduler bounds, cache normalization, turbo default and measured-first GMEM")
