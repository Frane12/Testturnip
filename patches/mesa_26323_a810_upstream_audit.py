#!/usr/bin/env python3
"""26.3.23: preserve A810 policy, remove duplicate evaluation, isolate caches."""
from pathlib import Path

R = Path('mesa/src/freedreno')

def edit(path, old, new):
    p = R / path
    s = p.read_text()
    assert s.count(old) == 1, (path, old[:100], s.count(old))
    p.write_text(s.replace(old, new, 1))

# Snapshot reference policies for the differential test before rewriting them.
for name in ['frane_mesa_26318_a810_smart_gmem.h',
             'frane_mesa_26320_a810_gmem_turbo.h']:
    p = R / 'vulkan' / name
    Path('/tmp/' + name + '.26322').write_text(p.read_text())

edit('vulkan/frane_mesa_26318_a810_smart_gmem.h',
     '''frane_26318_decide_smart_gmem(bool enabled,
                              const frane_26318_smart_gmem_input &in,''',
     '''frane_26323_decide_smart_gmem_evaluated(bool enabled,
                              const frane_26318_smart_gmem_eval &eval,''')
edit('vulkan/frane_mesa_26318_a810_smart_gmem.h',
     '   const auto eval = frane_26318_eval_smart_gmem(in);\n', '')
edit('vulkan/frane_mesa_26318_a810_smart_gmem.h', '\n#endif\n', '''
/* Evaluate once and share the result with the TURBO wrapper. */
static inline frane_26318_smart_gmem_decision
frane_26318_decide_smart_gmem(bool enabled,
                              const frane_26318_smart_gmem_input &in,
                              frane_2634_gmem_state state,
                              uint32_t probability, uint64_t decision_word)
{
   if (!enabled)
      return {};
   return frane_26323_decide_smart_gmem_evaluated(
      true, frane_26318_eval_smart_gmem(in), state, probability, decision_word);
}

#endif
''')
edit('vulkan/frane_mesa_26320_a810_gmem_turbo.h',
     '''   auto out = frane_26318_decide_smart_gmem(
      true, in, state, sysmem_probability, decision_word);''',
     '''   const auto eval = frane_26318_eval_smart_gmem(in);
   auto out = frane_26323_decide_smart_gmem_evaluated(
      true, eval, state, sysmem_probability, decision_word);''')
edit('vulkan/frane_mesa_26320_a810_gmem_turbo.h',
     '''   const auto eval = frane_26318_eval_smart_gmem(in);
   if (!eval.eligible)''', '   if (!eval.eligible)')

# Physical-device cache UUID is created before the logical IR3 compiler.
# Normalize exactly as ir3_compiler_create does, and use fixed-width fields:
# never hash struct padding or the spelling of an environment variable.
helper = '''static void
frane_26323_a810_cache_options(uint32_t options[10])
{
   int gap = debug_get_num_option("TU_A810_26310_UBO_GAP", 64);
   if (gap != 0 && gap != 32 && gap != 64 && gap != 128)
      gap = 64;
   unsigned window = debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 12);
   options[0] = gap;
   options[1] = debug_get_bool_option("TU_A810_26311_SAFE_TEX_PREFETCH", true);
   options[2] = debug_get_bool_option("TU_A810_26312_DUAL_TEX_PREFETCH", true);
   options[3] = debug_get_bool_option("TU_A810_26314_TRIPLE_TEX_PREFETCH", true);
   options[4] = debug_get_bool_option("TU_A810_26315_PREFETCH_DIVERSITY", true);
   options[5] = debug_get_bool_option("TU_A810_26315_QUAD_TEX_PREFETCH", true);
   options[6] = debug_get_bool_option("TU_A810_26316_PREFETCH_USE_SCORE", false);
   options[7] = debug_get_bool_option("TU_A810_26317_ADAPTIVE_SCHED", true);
   options[8] = MIN2(16u, MAX2(8u, window));
   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
}

'''
edit('vulkan/tu_device.cc', 'static int\ntu_device_get_cache_uuid',
     helper + 'static int\ntu_device_get_cache_uuid')
edit('vulkan/tu_device.cc',
     '''   _mesa_blake3_update(&ctx, &device->compiler_options,
                       sizeof(device->compiler_options));''',
     '''   _mesa_blake3_update(&ctx, &device->compiler_options,
                       sizeof(device->compiler_options));
   if (frane_2635_is_a810_chip(device->dev_id.chip_id)) {
      uint32_t options[10];
      frane_26323_a810_cache_options(options);
      static const char schema[] = "frane-a810-compile-options-v1";
      _mesa_blake3_update(&ctx, schema, sizeof(schema));
      _mesa_blake3_update(&ctx, options, sizeof(options));
   }''')

# IR3's own cache has a separate namespace. Hash resolved compiler fields,
# including the scheduler window which need not change the input NIR.
edit('ir3/ir3_disk_cache.c',
     '''   _mesa_blake3_update(&ctx, &compiler->options.uche_trap_base,
                     sizeof(compiler->options.uche_trap_base));''',
     '''   _mesa_blake3_update(&ctx, &compiler->options.uche_trap_base,
                     sizeof(compiler->options.uche_trap_base));
   const uint64_t frane_chip = compiler->dev_id->chip_id;
   if (frane_chip == UINT64_C(0x44010000) ||
       frane_chip == UINT64_C(0xffff44010000)) {
      const uint32_t options[] = {
         compiler->frane_26310_ubo_gap,
         compiler->frane_26311_safe_tex_prefetch,
         compiler->frane_26312_dual_tex_prefetch,
         compiler->frane_26314_triple_tex_prefetch,
         compiler->frane_26315_prefetch_diversity,
         compiler->frane_26315_quad_tex_prefetch,
         compiler->frane_26316_prefetch_use_score,
         compiler->frane_26317_adaptive_sched,
         compiler->frane_26317_tex_window_max,
      };
      static const char schema[] = "frane-a810-compile-options-v1";
      _mesa_blake3_update(&ctx, schema, sizeof(schema));
      _mesa_blake3_update(&ctx, options, sizeof(options));
   }''')
edit('vulkan/tu_device.cc', 'Frane Mesa 26.3.22 A810 LIVE-AUTOTUNE EXP / Mesa ',
     'Frane Mesa 26.3.23 A810 UPSTREAM-AUDIT EXP / Mesa ')
print('26.3.23: single-pass tile policy and compiler-option cache isolation applied')
