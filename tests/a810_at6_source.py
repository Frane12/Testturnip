#!/usr/bin/env python3
"""AT6 pinned runtime and scope checks; no unguarded override of safety."""
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
src=(v/"tu_autotune.cc").read_text()
hdr=(v/"frane_a810_at6.h").read_text()
device=(v/"tu_device.cc").read_text()
for s in ('debug_get_bool_option("TU_FRANE_AT6", true)',
          'return enabled && frane_a810_at5_enabled(device);',
          'frane_at6_decide(at1_in, snapshot, decision_word,',
          'at6 && context_eligible, &at6_applied',
          'at6_applied ? "AT6_CALIBRATED"',
          'frane_a810_rfc1_decision(', 'frane_a810_rfc1_timing(',
          'frane_a810_gmem_pass_safe(',
          'const render_mode before_frontier = mode;',
          'at5_applied ? "AT5_ADAPT"'):
    assert s in src,s
assert src.index('frane_a810_gmem_pass_safe(') < src.index('frane_a810_rfc1_decision(')
for s in ('at4.force_measure || at5.force_measure', 'const bool trusted',
          'paired >= 8', 's.volatility >= 5', 'FRANE_AT6_GMEM_BALANCED_REUSE',
          'out.force_measure = false', 's.stale[0]'):
    assert s in hdr,s
assert "A810 AT6 Calibrated Learner / Mesa" in device
assert "TU_FRANE_A810_RFC1_TRACE_PATH" in (v/"frane_a810_at4_rfc1.h").read_text()
print("AT6 source integration, safety order, trace independence and fallback PASS")
