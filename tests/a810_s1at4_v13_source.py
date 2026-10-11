#!/usr/bin/env python3
"""Static integration guard for pinned v1.3 Mesa source after overlay."""
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else 'mesa')/'src/freedreno/vulkan'
a=(v/'tu_autotune.cc').read_text()
d=(v/'tu_device.cc').read_text()
h=(v/'frane_a810_s1at4_coord.h').read_text()
for token in ('TU_FRANE_S1AT4_COORD','frane_s1at4_coordinate(',
              's1at4_coord_applied','S1_AT4_COORD','frane_at4_decide(',
              'frane_s1bp_trace(s1bp_seq,bp)',
              'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)'):
    assert token in a,token
assert a.index('frane_s1at4_coordinate(')<a.index('at3_sampling = at1.override_mode;')
assert 'at1.select_sysmem = runtime_decision.select_sysmem;' in a
assert 'at1.force_measure = false;' not in a
assert 'at1.override_mode = false;' not in a
assert a.index('frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)')<a.index('frane_s1bp_trace(s1bp_seq,bp)')
assert 'FRANE_S1AT4_MEASURE' in h and 'gpu_pairs >= 12 || gpu_score_abs >= 10' in h
assert 'Drnas-Turnip A810 S Ultimate v1.3' in d
assert 'Drnas-Turnip A810 S Ultimate v1.2' not in d
print('A810 v1.3 S1AT4 integration, probe vetoes and safety order PASS')
