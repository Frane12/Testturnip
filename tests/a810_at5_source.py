#!/usr/bin/env python3
"""Fail closed if AT5 leaks to other GPUs, breaks trace, or bypasses safety."""
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
src=(v/"tu_autotune.cc").read_text()
header=(v/"frane_a810_at5.h").read_text()
device=(v/"tu_device.cc").read_text()
for anchor in (
   'debug_get_bool_option("TU_FRANE_AT5", true)',
   'return enabled && frane_a810_s1at4_enabled(device);',
   'frane_at5_decide(at1_in, snapshot, decision_word, baseline)',
   'at5 && context_eligible, &at5_applied',
   'at5_applied ? "AT5_ADAPT"',
   'frane_a810_rfc1_decision(',
   'frane_a810_rfc1_timing(',
   'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)',
   'const render_mode before_frontier = mode;',
   'frane_s1at1_catalog_for(ctx).signature',
):
   assert anchor in src,anchor
assert src.index('frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)') < src.index('frane_a810_rfc1_decision(')
for a in ("paired >= 4", "paired >= 8", "at4.force_measure", "frane_at4_active", "s.stale[0]", "out.force_measure = true"):
   assert a in header,a
assert ("A810 AT5 Context Learner / Mesa" in device or
        "A810 AT6 Calibrated Learner / Mesa" in device)
assert "TU_FRANE_A810_RFC1_TRACE_PATH" in (v/"frane_a810_at4_rfc1.h").read_text()
print("A810 AT5 runtime selector, scope, policy fallback, optional trace and GMEM guard PASS")
