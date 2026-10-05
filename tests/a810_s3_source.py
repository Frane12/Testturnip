from pathlib import Path
import subprocess

root=Path('mesa')
patch=Path('patches/s1-smart2-complete.patch').read_text()
sections={}
for section in patch.split('diff --git ')[1:]:
    path=section.splitlines()[0].split(' b/',1)[1]
    sections[path]='diff --git '+section
normalize=lambda s:'\n'.join(x for x in s.splitlines() if not x.startswith('index '))
for path in ['src/freedreno/common/freedreno_devices.py',
             'src/freedreno/vulkan/tu_pass.cc',
             'src/freedreno/vulkan/tu_lrz.cc',
             'src/freedreno/vulkan/tu_knl_kgsl.cc']:
    actual=subprocess.check_output(['git','-C','mesa','diff','--',path],text=True)
    assert normalize(actual)==normalize(sections.get(path,'')),path
cmd=(root/'src/freedreno/vulkan/tu_cmd_buffer.cc').read_text()
at=(root/'src/freedreno/vulkan/tu_autotune.cc').read_text()
assert 'PIPE_BV_WAIT_FOR_BR' in cmd and 'PIPE_BR_WAIT_FOR_BV' in cmd
assert 'TU_ONCHIP_CB_RESLIST_OVERFLOW' in cmd
assert '!TU_DEBUG(NO_CONCURRENT_BINNING)' in cmd
assert 'frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)' in at
assert 'VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT' in at
assert 'history.frane_orch_word.load(std::memory_order_relaxed)' in at
assert 'if (!entry.frane_orch_sample && entry.frane_smart_sample' in at
cache=(root/'src/freedreno/ir3/ir3_disk_cache.c').read_text()
for field in ['frane_26310_ubo_gap','frane_26311_safe_tex_prefetch',
              'frane_26312_dual_tex_prefetch','frane_26314_triple_tex_prefetch',
              'frane_26315_quad_tex_prefetch','frane_26315_prefetch_diversity',
              'frane_26316_prefetch_use_score','frane_26317_adaptive_sched',
              'frane_26317_tex_window_max']:
    assert 'compiler->'+field in cache,field
print('PASS S3 source: pre-S2 A810 hardware/CCU, GMEM allocator, LRZ and KGSL unchanged; CB synchronization, overflow checks and final GMEM safety retained; all compiler options in shader-cache key')
