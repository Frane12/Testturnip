#!/usr/bin/env python3
"""Fail-closed checks for actual Mesa source integration."""
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
a=(v/"tu_autotune.cc").read_text()
p=(v/"tu_pipeline.cc").read_text()
d=(v/"tu_device.cc").read_text()
for s in ("TU_FRANE_V3_COLD_FASTPATH","frane_v3_no_possible_candidate(",
          "frane_atu_v3_step(","TU_FRANE_S1AT4_COORD",
          "frane_a810_gmem_pass_safe("):
    assert s in a,s
assert a.index("frane_v3_no_possible_candidate(")<a.index("frane_atu_v3_step(")
assert a.index("frane_atu_v3_step(")<a.index("frane_at8_early_winner(")
for s in ("frane_pipeline_begin()","frane_pipeline_end(","\"GRAPHICS\"",
          "\"COMPUTE\"","TU_GENX(tu_CreateGraphicsPipelines)",
          "TU_GENX(tu_CreateComputePipelines)"):
    assert s in p,s
assert p.count("frane_pipeline_begin()")==2
assert p.count("frane_pipeline_end(")==2
assert "Drnas-Turnip A810 S Ultimate v1.5" in d
print("S Ultimate v1.5 V3 cold fastpath, two pipeline probes, safety and branding PASS")
