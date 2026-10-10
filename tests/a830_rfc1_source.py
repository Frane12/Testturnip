#!/usr/bin/env python3
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
s=(V/"frane_mesa_26318_a810_smart_gmem.h").read_text()
a=(V/"frane_a830_v2_adaptive_gmem.h").read_text()
auto=(V/"tu_autotune.cc").read_text()
dev=(V/"tu_device.cc").read_text()
cmd=(V/"tu_cmd_buffer.cc").read_text()
rfc=(V/"frane_a830_rfc1.h").read_text()
assert 'frane_a830_s2bw2_evaluate(' in auto
assert 'const auto bw2 = in.a830_rfc_has_cache ? in.a830_rfc_cached_bw2 :' in s
assert 'const auto bw2 = in.a830_rfc_has_cache ? in.a830_rfc_cached_bw2 :' in a
assert 'TU_FRANE_A830_RFC1", true' in auto
assert 'runtime_input.a830_bw2 && frane_a830_rfc1_enabled(device)' in auto
assert 'TU_FRANE_A830_TRACE_PATH' in rfc
assert 'frane_a830_rfc1_trace(' in auto
assert 'mode == render_mode::SYSMEM, measure' in auto
assert 'frane_26320_a830_gpu(device)' in auto
assert ('Turnip-Drnas A830 S2-RFC1 Render Features / Mesa ' in dev or
        'Turnip-Drnas A830 S2-RFC2 Measured Render / Mesa ' in dev)
assert 'TU_FRANE_A830_BW3' not in auto
assert 'TU_FRANE_A830_CX1' not in auto
assert "frane_a830_s2bw2_evaluate" in s and "frane_a830_s2bw2_evaluate" in a
assert 'bw2.rollback_sysmem' in a
f=cmd[cmd.index("static bool\nuse_sysmem_rendering"):
      cmd.index("/* Optimization: there is no reason to load gmem")]
assert f.index("A830 GMEM disabled by TU_FRANE_A830_GMEM=0") < f.index("if (TU_DEBUG(GMEM))")
for guard in ("!pass->has_msrtss", "!pass->has_fdm",
              "!pass->subpasses[i].resolve_depth_stencil",
              "att.samples == VK_SAMPLE_COUNT_1_BIT"):
    assert guard in f, guard
print("A830 RFC1 exact device, no BW3/CX1, and GMEM safety tests PASS")
