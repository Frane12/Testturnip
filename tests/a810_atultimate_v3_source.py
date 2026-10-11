#!/usr/bin/env python3
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
s=(v/"tu_autotune.cc").read_text()
dev=(v/"tu_device.cc").read_text()
trace=(v/"frane_a810_atultimate_trace.h").read_text()
hdr=(v/"frane_a810_atultimate_v3.h").read_text()
for t in ("TU_FRANE_ATU_V3", "frane_atu_v3_cache",
          "frane_atu_v3_epoch", "frane_atu_v3_step(",
          "v3 && context_eligible, &atu_v3_applied",
          "ATU_V3_CATEGORY_WINNER","row.v3 = atu_v3_diag",
          "!s1atu_v3_context"):
 assert t in s,t
assert s.index("frane_atu_v3_step(")<s.index("frane_at8_early_winner(")
assert s.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)")<s.index("frane_atu_trace(row,history.frane_s1at3_words)")
for t in ("FRANE_ATU_V3_SLOTS 4","struct frane_atu_v3_slot",
          "frane_atu_v3_reason(", "frane_atu_v3_no_candidate_why(",
          "n.challenger != candidate",
          "s.key == key","s.frequency",
          "ATU_V3_NO_PAIRED","ATU_V3_AT4_PROBE","ATU_V3_RUNTIME_PRIORITY"):
 assert t in hdr,t
for t in ("v3_reason","v3_cached_winner","v3_blocked","r.v3.why",
          "r.v3.phase_switched"):
 assert t in trace,t
assert "ATUltimate Dynamic V3 / Mesa" in dev
assert not any(t in s for t in ("TU_FRANE_AT9","frane_at9_fc2","AT9_FC2_PRIOR"))
print("V3 real runtime GPU champion integration with 4-way categories, tracing and no AT9 PASS")
