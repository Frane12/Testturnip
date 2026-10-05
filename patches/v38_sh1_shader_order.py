from pathlib import Path
import hashlib

root = Path('mesa/src/freedreno')
allowed = {'ir3/ir3_compiler.c', 'ir3/ir3_compiler.h', 'ir3/ir3_sched.c',
           'ir3/ir3_disk_cache.c', 'ir3/frane_sh1_policy.h', 'vulkan/tu_device.cc'}
before = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in root.rglob('*') if p.is_file()}

def edit(rel, old, new):
    p = root / rel
    s = p.read_text()
    if s.count(old) != 1:
        raise SystemExit(f'SH1 source drift: {rel}: {old[:120]!r}')
    p.write_text(s.replace(old, new, 1))

policy = Path('patches/frane_sh1_policy.h').read_text()
(root / 'ir3/frane_sh1_policy.h').write_text(policy)
edit('ir3/ir3_compiler.c', '#include "ir3_compiler.h"',
     '#include "ir3_compiler.h"\n#include "frane_sh1_policy.h"')
edit('ir3/ir3_sched.c', '#include "ir3_compiler.h"',
     '#include "ir3_compiler.h"\n#include "frane_sh1_policy.h"')
edit('vulkan/tu_device.cc', '#include "tu_device.h"',
     '#include "tu_device.h"\n#include "../ir3/frane_sh1_policy.h"')
edit('ir3/ir3_compiler.h', '   uint8_t frane_26317_tex_window_max;',
     '   uint8_t frane_26317_tex_window_max;\n   uint8_t frane_sh1_mode;\n   uint8_t frane_sh1_threshold;')
edit('ir3/ir3_compiler.c',
     '         MIN2(8u, MAX2(2u, frane_tex_window));',
     '''         MIN2(8u, MAX2(2u, frane_tex_window));
      compiler->frane_sh1_mode = frane_sh1_mode(
         debug_get_num_option("TU_FRANE_SHADER_MODE", 1));
      compiler->frane_sh1_threshold = frane_sh1_threshold(
         debug_get_num_option("TU_FRANE_SHADER_PRESSURE", 35));''')

for fn, end in [('choose_instr_dec', 'enum choose_instr_inc_rank'),
                ('choose_instr_inc', 'static struct ir3_sched_node *\nchoose_instr_prio')]:
    p = root / 'ir3/ir3_sched.c'
    s = p.read_text()
    start = s.index('\n' + fn + '(struct ir3_sched_ctx *ctx')
    stop = s.index(end, start)
    body = s[start:stop]
    assert body.count('ctx->compiler->frane_26317_adaptive_sched') == (2 if fn == 'choose_instr_dec' else 3)
    body = body.replace('   const char *mode = defer ? "-d" : "";',
        '''   const char *mode = defer ? "-d" : "";
   const bool pressure_priority = frane_sh1_pressure_priority(
      ctx->compiler->frane_26317_adaptive_sched,
      ctx->compiler->frane_sh1_mode, frane_26317_pressure_pct(ctx),
      ctx->compiler->frane_sh1_threshold);''', 1)
    prefix, rest = body.split('   struct ir3_sched_node *chosen = NULL;', 1)
    rest = rest.replace('ctx->compiler->frane_26317_adaptive_sched',
                        'pressure_priority')
    body = prefix + '   struct ir3_sched_node *chosen = NULL;' + rest
    p.write_text(s[:start] + body + s[stop:])

edit('vulkan/tu_device.cc', 'frane_26323_a810_cache_options(uint32_t options[10])',
     'frane_26323_a810_cache_options(uint32_t options[12])')
edit('vulkan/tu_device.cc',
     '   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);',
     '''   options[9] = debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);
   options[10] = frane_sh1_mode(debug_get_num_option("TU_FRANE_SHADER_MODE", 1));
   options[11] = frane_sh1_threshold(debug_get_num_option("TU_FRANE_SHADER_PRESSURE", 35));''')
edit('vulkan/tu_device.cc', '      uint32_t options[10];',
     '      uint32_t options[12];')
edit('vulkan/tu_device.cc', 'frane-a810-compile-options-v1',
     'frane-a810-v38-sh1-compile-options-v1')
edit('ir3/ir3_disk_cache.c',
     '         compiler->frane_26317_tex_window_max,',
     '''         compiler->frane_26317_tex_window_max,
         compiler->frane_sh1_mode,
         compiler->frane_sh1_threshold,''')
edit('ir3/ir3_disk_cache.c', 'frane-a810-compile-options-v1',
     'frane-a810-v38-sh1-compile-options-v1')
edit('vulkan/tu_device.cc', 'Turnip A810 V38 / Mesa ',
     'Turnip-Drnas A810 V38 SH1 / Mesa ')

after = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in root.rglob('*') if p.is_file()}
changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
assert changed == allowed, changed
print('SH1: shader scheduler and both compiler cache identities changed; scope verified')
