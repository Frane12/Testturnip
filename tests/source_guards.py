from pathlib import Path
v=Path('mesa/src/freedreno/vulkan')
s=(v/'tu_cmd_buffer.cc').read_text()
f=s[s.index('static bool\nuse_sysmem_rendering'):s.index('/* Optimization: there is no reason to load gmem')]
assert f.index('A830 GMEM disabled by TU_FRANE_A830_GMEM=0') < f.index('if (TU_DEBUG(GMEM))') < f.index('autotune->get_optimal_mode')
assert 'debug_get_bool_option("TU_FRANE_A830_GMEM", true)' in f
for gate in ['!pass->has_msrtss','!pass->has_fdm','framebuffer->layers == 1','pass->num_views <= 1','att.samples == VK_SAMPLE_COUNT_1_BIT','!att.will_be_resolved','att.gmem_offset_stencil[layout]','!pass->subpasses[i].custom_resolve','!pass->subpasses[i].resolve_depth_stencil']:
 assert gate in f,gate
s=(v/'tu_autotune.cc').read_text()
start=s.index('         bool frane_smart = false, uint32_t occurrence = 0,')
end=s.index('   } profiled;', start)
f=s[start:end]
assert f.index('frane_26364_select(') < f.index('frane_2633_decision_draw(') < f.index('measurement_ticket.fetch_add(')
assert '*measure = d.measure;' in f and 'a830_v2_flags = 0;' in f
assert '(*rp_ctx)->frane_smart_occurrence = occurrence;' in s
assert 'debug_get_bool_option("TU_FRANE_SMART", true)' in s
s=(v/'tu_device.cc').read_text()
assert s.index('frane_a830_cache_fits(device->gmem_size') < s.index('fd6_calc_gmem_cache_offsets(&info')
s=(v/'tu_suballoc.cc').read_text();assert 'suballoc->bo = NULL;' in s
s=(v/'tu_knl_kgsl.cc').read_text()
for token in ['munmap','ION_IOC_FREE','close(share.fd)','IOCTL_KGSL_GPUMEM_FREE_ID']: assert token in s
print('A830 source guards: PASS (GMEM default-on, TU_FRANE_A830_GMEM=0 fallback, debug ordering, scope, early ownership, cache underflow, KGSL cleanup)')

s=(v/'tu_autotune.cc').read_text()
f=s[s.index('tu_autotune::rp_key::rp_key(const struct tu_render_pass *pass,'):s.index('tu_autotune::rp_key::rp_key(const rp_key &key,')]
for token in ['scope_words = a830_scope ? 8u : 0u', 'area.offset.x', 'area.offset.y', 'area.extent.width', 'area.extent.height', 'pass->autotune_hash >> 32', 'draws ? 32u - __builtin_clz(draws) : 0u', 'uint32_t(cmd->state.gmem_layout)', '3 + scope_words']:
 assert token in f,token
assert f.count('*ptr++')==11
print('A830 history signature: PASS (GPU scoped, area, pass structure, draw bucket, layout; fixed key capacity)')
