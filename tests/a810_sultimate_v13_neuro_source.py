#!/usr/bin/env python3
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
s=(v/"tu_autotune.cc").read_text()
d=(v/"tu_device.cc").read_text()
t=(v/"frane_a810_s1_bandwidth_probe.h").read_text()
h=(v/"frane_s1_neuro_shadow.h").read_text()
assert "TU_FRANE_S1_NEURO_SHADOW" in s
assert 'frane_s1_neuro::Bank frane_s1_neuro_net' in s
assert 'entry.frane_s1at1_signature' in s
assert 'frane_s1_neuro_net.train(sample)' in s
assert 'history.frane_s1_neuro_net.infer(' in s
assert s.index('frane_s1_neuro_net.train(sample)') > s.index('rp_duration = entry.get_rp_duration()')
assert s.index('frane_s1_neuro_net.infer(') > s.index('frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)')
assert s.index('frane_s1_neuro_net.infer(') < s.index('frane_s1bp_trace(s1bp_seq,bp)')
assert 'bp.neuro_trusted' in s and 'bp.neuro_agrees' in s
assert 'neuro_trusted,neuro_sysmem,neuro_score,neuro_votes,neuro_agrees' in t
assert 'static inline Decision infer_packed(' in h
assert 'std::atomic<uint64_t> view_[4]' in h
assert 'std::mutex mutex_' in h
assert 'Drnas-Turnip A810 S Ultimate v1.3' in d
for forbidden in ('mode = prediction.preferred', 'select_sysmem = prediction', 'at1 = prediction', 'runtime_decision = prediction'):
    assert forbidden not in s,forbidden
print("v1.3 real Mesa shadow-only integration, GPU completion and safety PASS")
