#!/usr/bin/env python3
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
a=(v/"tu_autotune.cc").read_text()
dev=(v/"tu_device.cc").read_text()
p=(v/"frane_a810_atultimate.h").read_text()
log=(v/"frane_a810_atultimate_trace.h").read_text()
for token in (
 'debug_get_bool_option("TU_FRANE_ATU", true)',
 'return on && frane_a810_at8_enabled(d);',
 'frane_atu_protect_prior(',
 'atu && context_eligible, &atu_prior_rejected',
 'frane_atu_trace(row,history.frane_s1at3_words)',
 'history.frane_atu_occurrence.fetch_add(',
 'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)',
 'frane_a810_rfc1_decision(',
 'ATU_HISTORY_GUARD'
):
 assert token in a,token
assert 'ATUltimate Context Learner / Mesa' in dev
assert 'TU_FRANE_ATU_CONTEXT_TRACE_PATH' in log
for token in ('TABLE','DECISION','SLOT_SNAPSHOT','MEASURED_DISAGREEMENT',
 'CONTEXT_MISS','STALE_HISTORY','PRIOR_CONFLICT_BLOCKED','static std::mutex',
 'slots[i].load(std::memory_order_relaxed)','75000u'):
 assert token in log,token
for token in ('s.at7_saving_4us >= 40','s.at7_noise_q8 <= 80','s.volatility <= 3',
 'return {}; /* Fall back','!s.stale[0] && !s.stale[1]'):
 assert token in p,token
assert a.index('frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)') < a.index('frane_atu_trace(row,history.frane_s1at3_words)')
assert not any(x in a for x in ('TU_FRANE_AT9','frane_at9_fc2','AT9_FC2_PRIOR'))
print('ATUltimate: no AT9, guarded measured-history policy, separate context CSV, real final decisions PASS')
