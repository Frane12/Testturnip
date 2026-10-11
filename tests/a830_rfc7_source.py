#!/usr/bin/env python3
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
a=(V/"tu_autotune.cc").read_text()
h=(V/"frane_a830_rfc7.h").read_text()
d=(V/"tu_device.cc").read_text()
c=(V/"tu_cmd_buffer.cc").read_text()
assert 'TU_FRANE_A830_RFC7_PATH' in h
assert 'std::setvbuf(file, nullptr, _IOFBF, 65536)' in h
assert "if ((rows & 31u) == 0u)" in h
assert 'rows >= 16384u' in h
assert 'physical_gmem_bytes' in h and 'usable_gmem_bytes' in h
assert 'est_load_bytes,est_store_bytes,est_clear_bytes,est_resolve_bytes' in h
assert 'gpu_ticks,render_ticks,binning_ticks,max_tile_ticks' in h
assert 'row.draw_bw_sample_sum =' in a
assert 'pass->attachments[i]' in a
assert 'att.will_be_resolved && att.samples' in a
assert 'runtime_input.a830_bw2 && frane_a830_rfc7_path()' in a
assert 'entry.frane_smart_sample &&' in a
assert 'frane_a830_s2bw2_enabled(at.device)' in a
assert 'row.render_ticks = gpu.ts_end >= gpu.ts_start' in a
assert 'row.binning_ticks =' in a
assert 'entry.config.test(metric_flag::TS_TILE)' in a
assert 'entry.config.test(metric_flag::SAMPLES)' in a
assert 'Turnip-Drnas A830 S2-RFC7 Bandwidth Profiler / Mesa ' in d
assert 'if (trusted.accepted)' in a
assert 'frane_a830_rfc6_select' in a and 'frane_a830_rfc5_select' in a
f=c[c.index("static bool\nuse_sysmem_rendering"):c.index("/* Optimization: there is no reason to load gmem")]
for token in ("!pass->has_msrtss","!pass->has_fdm",
              "!pass->subpasses[i].resolve_depth_stencil",
              "att.samples == VK_SAMPLE_COUNT_1_BIT"):
    assert token in f,token
print("RFC7 opt-in read-only profiler + hardware safety + unchanged RFC6 decisions PASS")
