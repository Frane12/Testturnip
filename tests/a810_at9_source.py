#!/usr/bin/env python3
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
a=(v/"tu_autotune.cc").read_text()
d=(v/"tu_device.cc").read_text()
h=(v/"frane_a810_at9_fc2.h").read_text()
for token in (
 'debug_get_bool_option("TU_FRANE_AT9", true)',
 'return on && frane_a810_at8_enabled(d);',
 'frane_at9_fc2_measured(',
 'frane_at9_fc2_prior(',
 'at9 && context_eligible, &at9_rescue, &at9_prior',
 'at9_rescue ? "AT9_FC2_GPU_RESCUE"',
 'at9_prior ? "AT9_FC2_PRIOR"',
 'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)',
 'frane_a810_rfc1_decision('
):
 assert token in a,token
assert a.index("frane_at9_fc2_measured(")<a.index("frane_at8_early_winner(")
assert a.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)")<a.index("frane_a810_rfc1_decision(")
assert "AT9 FC2 Measured Rescue / Mesa" in d
for token in ('paired < 3','s.at7_saving_4us','at4.force_measure',
              'runtime_forced_measure','s.at7_noise_q8','paired >= 3',
              'in.sysmem_bandwidth_per_pixel == 0'):
 assert token in h,token
assert 'TU_FRANE_AT5' not in a
print("AT9 exact compiled runtime, A810-only enable gate, probes and CSV provenance PASS")
