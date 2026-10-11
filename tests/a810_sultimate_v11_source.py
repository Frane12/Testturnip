#!/usr/bin/env python3
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
s=(v/"tu_autotune.cc").read_text(); h=(v/"frane_a810_atultimate_v3.h").read_text(); d=(v/"tu_device.cc").read_text()
for t in ('!at1.override_mode && !at1.force_measure','!runtime_decision.force_measure','v3_safe_enabled','v3_safe);'):
 assert t in s,t
for t in ('ATU_V3_SAFETY_VETO','!may_override || at4_probe || runtime_override','bool safety_ok = true'):
 assert t in h,t
assert 'Drnas-Turnip A810 S Ultimate v1.1' in d
assert s.index('frane_atu_v3_step(')<s.index('frane_at8_early_winner(')
assert s.index('frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)')<s.index('frane_atu_trace(row,history.frane_s1at3_words)')
print('S Ultimate v1.1 source audit PASS')
