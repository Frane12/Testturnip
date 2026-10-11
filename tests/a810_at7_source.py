#!/usr/bin/env python3
from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")
v=root/"src/freedreno/vulkan"
auto=(v/"tu_autotune.cc").read_text()
his=(v/"frane_s1at3_fast.h").read_text()
dev=(v/"tu_device.cc").read_text()
rfc=(v/"frane_a810_at4_rfc1.h").read_text()
for token in (
 'debug_get_bool_option("TU_FRANE_AT7", true)',
 'return on && frane_a810_at63_enabled(d);',
 'frane_at7_utility_winner(',
 's1at7_context && s1at63_context',
 'at7 && context_eligible, &at7_applied',
 'at7_applied ? "AT7_UTILITY_WINNER"',
 'at63_applied ? "AT63_EARLY_WINNER"',
 'at6_applied ? "AT6_AT4BASE"',
 'frane_a810_rfc1_timing(',
 'const render_mode before_frontier = mode;',
 'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)',
):
 assert token in auto,token
assert auto.index("frane_at7_utility_winner(")<auto.index("frane_at63_measured_winner(")
assert auto.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)")<auto.index("frane_a810_rfc1_decision(")
assert "TU_FRANE_AT5" not in auto and not (v/"frane_a810_at5.h").exists()
for token in ("at7_saving_4us","at7_noise_q8","lower_bound_ticks / 77u","(saving_q4us << 40)","(word >> 52) & 255u"):
 assert token in his,token
assert "frane_a810_rfc1_ticks_to_ns" in rfc
assert ("AT7 Utility Winner / Mesa" in dev or
        "AT8 Early GPU Winner / Mesa" in dev or
        "ATUltimate Context Learner / Mesa" in dev)
print("AT7 actual call-site, AT63 rollback, no AT5, safety gate and optional ns CSV PASS")
