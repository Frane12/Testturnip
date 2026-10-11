#!/usr/bin/env python3
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
auto=(V/"tu_autotune.cc").read_text()
h=(V/"frane_a830_rfc4.h").read_text()
r=(V/"frane_a830_rfc2.h").read_text()
smart=(V/"frane_mesa_26318_a810_smart_gmem.h").read_text()
device=(V/"tu_device.cc").read_text()
assert 'TU_FRANE_A830_RFC4", true' in auto
assert 'return enabled && frane_26320_a830_gpu(device)' in auto
assert 'runtime_input.a830_rfc3 && frane_a830_rfc4_enabled(device)' in auto
assert "bool a830_rfc4 = false;" in smart
assert "frane_a830_rfc4_vol_word" in auto
assert "frane_a830_rfc4_update_volatility" in auto
assert "previous_average" in auto and "previous_count" in auto
assert "frane_a830_rfc4_select(" in auto
assert "history.frane_a830_rfc4_vol_word.load(" in auto
assert "else if (gmem_runtime_input->a830_rfc3)" in auto
assert auto.index("frane_a830_rfc4_select(") < auto.index("const auto d = frane_26364_select(")
assert "FRANE_A830_RFC2_REGIME_LEARNED" in r
assert "REGIME_AUDIT" in r
assert "version,session_id,event" in r
assert "gpu_ticks,sys_ema_ticks,gmem_ema_ticks" in r
assert "measured_events.fetch_add" in r
assert "clock_gettime(CLOCK_MONOTONIC" in r
assert ("Turnip-Drnas A830 S2-RFC4 Adaptive Learning / Mesa " in device or
        "Turnip-Drnas A830 S2-RFC5 Hotspot Learning / Mesa " in device or
        "Turnip-Drnas A830 S2-RFC6 Confidence Learning / Mesa " in device)
assert "frane_a830_s2bw2_ratio_le" in h
assert "sys_average_ticks" in h and "gm_average_ticks" in h
assert "volatility >= 35u" in h
assert "measure_log2 = 5u" in h and "audit_log2 = 6u" in h
assert "TU_FRANE_A830_BW3" not in auto
print("RFC4 integration + session trace + conservative GMEM/SYSMEM policy PASS")
