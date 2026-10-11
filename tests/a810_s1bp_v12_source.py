#!/usr/bin/env python3
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
a=(v/"tu_autotune.cc").read_text()
h=(v/"frane_a810_s1_bandwidth_probe.h").read_text()
d=(v/"tu_device.cc").read_text()
for s in ("frane_s1bp_take_sample()","frane_s1bp_trace(s1bp_seq,bp)",
          "*s1_override_out = runtime_decision.override_mode",
          "&s1_runtime_override, &s1_runtime_sysmem",
          "frane_atu_v3_step(","frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)"):
    assert s in a,s
assert a.index("frane_atu_v3_step(")<a.index("frane_s1bp_trace(s1bp_seq,bp)")
assert a.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)")<a.index("frane_s1bp_trace(s1bp_seq,bp)")
for s in ("TU_FRANE_S1BP_TRACE_PATH","entries[N][640]","frane_s1bp_estimate",
          "std::fflush(file)","std::mutex mutex","sys_est_known"):
    assert s in h,s
assert "Drnas-Turnip A810 S Ultimate v1.2" in d
assert "Drnas-Turnip A810 S Ultimate v1.1" not in d
print("S Ultimate v1.2 buffered profiling, safety order and branding PASS")
