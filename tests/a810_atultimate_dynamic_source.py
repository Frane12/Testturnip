#!/usr/bin/env python3
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
a=(v/"tu_autotune.cc").read_text();dev=(v/"tu_device.cc").read_text()
h=(v/"frane_a810_atultimate_dynamic.h").read_text()
trace=(v/"frane_a810_atultimate_trace.h").read_text()
for token in ('TU_FRANE_ATU_DYNAMIC','TU_FRANE_ATU_FAST',
              'TU_FRANE_ATU_PHASE_HITS','TU_FRANE_ATU_DWELL',
              'frane_atu_dyn_step(', 'history.frane_atu_dynamic_word',
              'dynamic && context_eligible, &atu_dynamic_applied',
              'ATU_DYNAMIC_WINNER',
              'row.dynamic = atu_dynamic_diag',
              'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)'):
 assert token in a,token
assert a.index('frane_atu_dyn_step(')<a.index('at3_sampling = at1.override_mode;')
assert a.index('frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)')<a.index('frane_atu_trace(row,history.frane_s1at3_words)')
for token in ('compare_exchange_weak','s.pending == signature','n.hits >= stable_hits',
              'n.cooldown = uint8_t(dwell)', 'n.votes >= required+3u',
              '!candidate','s.at7_saving_4us >= 150','pairs >= 3'):
 assert token in h,token
for token in ('dyn_active','dyn_winner','dyn_votes','dyn_cooldown',
              'r.dynamic.phase_switch','r.dynamic.winner_switch'):
 assert token in trace,token
assert ('A810 ATUltimate Dynamic V2 / Mesa' in dev or
        'A810 ATUltimate Dynamic V3 / Mesa' in dev or
        'A810 S Ultimate v1.0 / Mesa' in dev)
assert not any(t in a for t in ('TU_FRANE_AT9','frane_at9_fc2','AT9_FC2_PRIOR'))
print('ATUltimate V2 actual selector + context table, no AT9, fast and hysteresis feature flags PASS')
