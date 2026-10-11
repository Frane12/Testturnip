#!/usr/bin/env python3
"""S Ultimate v1.0 RC: final source/runtime integration and safety checks."""
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa")/"src/freedreno/vulkan"
dev=(v/"tu_device.cc").read_text()
auto=(v/"tu_autotune.cc").read_text()
hdr=(v/"frane_a810_atultimate_v3.h").read_text()
for t in (
  'TU_FRANE_ULTIMATE_HUD_BRAND',
  'Drnas-Turnip A810 S Ultimate v1.0',
  'Drnas-Turnip A810 S Ultimate v1.0 / Mesa',
  'pdevice->instance->drirc.debug.force_vk_devicename',
  'pdevice->dev_id.chip_id == 0x44010000ull',
  'pdevice->dev_id.chip_id == 0xffff44010000ull',
  'pdevice->name'):
    assert t in dev,t
assert 'VK_DRIVER_ID_MESA_TURNIP' in dev
for t in (
 'TU_FRANE_ATU_V3','TU_FRANE_ATU_DYNAMIC',
 'frane_atu_v3_step(', 'frane_atu_v3_cache',
 'frane_atu_v3_epoch', 'ATU_V3_CATEGORY_WINNER',
 'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)',
 'frane_atu_trace(row,history.frane_s1at3_words)'):
    assert t in auto,t
assert auto.index('frane_atu_v3_step(') < auto.index('frane_at8_early_winner(')
assert auto.index('frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)') < auto.index('frane_atu_trace(row,history.frane_s1at3_words)')
assert 'if (s.active == signature) {' in hdr
assert 'n.pending = 0;' in hdr and 'n.hits = 0;' in hdr
assert 'const bool still_active = phase_ready &&' in hdr
assert '!s1atu_v3_context' in auto
assert not any(t in auto for t in ('TU_FRANE_AT9','frane_at9_fc2','AT9_FC2_PRIOR'))
print('S Ultimate v1.0 RC A810-only Vulkan HUD brand, device UUID/IDs, '
      'AT4 protection, phase & cache safety, opt-out baseline PASS')
