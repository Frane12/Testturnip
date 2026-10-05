from pathlib import Path
import hashlib

root = Path('mesa/src/freedreno')
allowed = {'ir3/ir3_compiler.c', 'ir3/ir3_compiler.h', 'ir3/ir3_sched.c',
           'ir3/ir3_disk_cache.c', 'ir3/frane_sh2_policy.h', 'vulkan/tu_device.cc'}
before = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in root.rglob('*') if p.is_file()}

def edit(rel, old, new):
    p = root / rel
    s = p.read_text()
    if s.count(old) != 1:
        raise SystemExit(f'SH2 source drift: {rel}: {old[:120]!r}')
    p.write_text(s.replace(old, new, 1))

(root / 'ir3/frane_sh2_policy.h').write_text(
    Path('patches/frane_sh2_policy.h').read_text())
for rel in ('ir3/ir3_compiler.c', 'ir3/ir3_sched.c'):
    edit(rel, '#include "frane_sh1_policy.h"',
         '#include "frane_sh1_policy.h"\n#include "frane_sh2_policy.h"')
edit('vulkan/tu_device.cc', '#include "../ir3/frane_sh1_policy.h"',
     '#include "../ir3/frane_sh1_policy.h"\n#include "../ir3/frane_sh2_policy.h"')
edit('ir3/ir3_compiler.h', '   uint8_t frane_sh1_threshold;',
     '''   uint8_t frane_sh1_threshold;
   bool frane_sh2_critical;
   bool frane_sh2_sfu;
   uint8_t frane_sh2_sfu_window;''')
edit('ir3/ir3_compiler.c',
     '         debug_get_num_option("TU_FRANE_SHADER_PRESSURE", 35));',
     '''         debug_get_num_option("TU_FRANE_SHADER_PRESSURE", 35));
      compiler->frane_sh2_critical =
         debug_get_bool_option("TU_FRANE_SHADER_CRITICAL", true);
      compiler->frane_sh2_sfu =
         debug_get_bool_option("TU_FRANE_SHADER_SFU", true);
      compiler->frane_sh2_sfu_window = frane_sh2_sfu_window(
         debug_get_num_option("TU_FRANE_SHADER_SFU_WINDOW", 6));''')
edit('ir3/ir3_sched.c',
     'static bool\nshould_defer(struct ir3_sched_ctx *ctx, struct ir3_instruction *instr)',
     '''static unsigned
frane_sh2_ss_limit(struct ir3_sched_ctx *ctx)
{
   if (!ctx->compiler->frane_26317_adaptive_sched ||
       !ctx->compiler->frane_sh1_mode || !ctx->compiler->frane_sh2_sfu)
      return 8u;

   return frane_sh2_ss_window(frane_26317_pressure_pct(ctx),
                              ctx->compiler->frane_sh1_threshold,
                              ctx->compiler->frane_sh2_sfu_window);
}

static bool
should_defer(struct ir3_sched_ctx *ctx, struct ir3_instruction *instr)''')
edit('ir3/ir3_sched.c',
     '   /* Keep the SFU queue at the upstream cap.  This experiment deliberately\n    * changes only the texture/memory (sy) side first.\n    */\n', '')
edit('ir3/ir3_sched.c',
     '   if (ctx->ss_index - ctx->first_outstanding_ss_index >= 8 && is_ss_producer(instr))',
     '''   if ((unsigned)(ctx->ss_index - ctx->first_outstanding_ss_index) >=
          frane_sh2_ss_limit(ctx) && is_ss_producer(instr))''')

for fn, end in [('choose_instr_dec', 'enum choose_instr_inc_rank'),
                ('choose_instr_inc', 'static struct ir3_sched_node *\nchoose_instr_prio')]:
    p = root / 'ir3/ir3_sched.c'
    s = p.read_text()
    start = s.index('\n' + fn + '(struct ir3_sched_ctx *ctx')
    stop = s.index(end, start)
    body = s[start:stop]
    old = '   struct ir3_sched_node *chosen = NULL;'
    assert body.count(old) == 1
    body = body.replace(old, '''   const unsigned sh2_pressure = frane_26317_pressure_pct(ctx);
   const bool sh2_critical = ctx->compiler->frane_26317_adaptive_sched &&
      ctx->compiler->frane_sh1_mode && ctx->compiler->frane_sh2_critical &&
      !pressure_priority;
   int64_t chosen_score = 0;
   struct ir3_sched_node *chosen = NULL;''', 1)
    anchor = '      if (!better && rank == chosen_rank) {'
    assert body.count(anchor) == 1
    if fn == 'choose_instr_inc':
        body = body.replace('int live_growth = pressure_priority ?',
                            'int live_growth = (pressure_priority || sh2_critical) ?', 1)
    live = 'live' if fn == 'choose_instr_dec' else 'live_growth'
    distance = '0u' if fn == 'choose_instr_dec' else 'distance'
    body = body.replace(anchor, f'''      int64_t sh2_score = 0;
      if (sh2_critical)
         sh2_score = frane_sh2_score(sh2_pressure, n->max_delay,
                                     {distance}, {live});

      if (!better && rank == chosen_rank && sh2_critical &&
          sh2_score != chosen_score) {{
         better = sh2_score > chosen_score;
      }} else if (!better && rank == chosen_rank) {{''', 1)
    body = body.replace('         chosen = n;',
                        '         chosen = n;\n         chosen_score = sh2_score;', 1)
    p.write_text(s[:start] + body + s[stop:])

edit('vulkan/tu_device.cc', 'frane_26323_a810_cache_options(uint32_t options[12])',
     'frane_26323_a810_cache_options(uint32_t options[15])')
edit('vulkan/tu_device.cc',
     '   options[11] = frane_sh1_threshold(debug_get_num_option("TU_FRANE_SHADER_PRESSURE", 35));',
     '''   options[11] = frane_sh1_threshold(debug_get_num_option("TU_FRANE_SHADER_PRESSURE", 35));
   options[12] = debug_get_bool_option("TU_FRANE_SHADER_CRITICAL", true);
   options[13] = debug_get_bool_option("TU_FRANE_SHADER_SFU", true);
   options[14] = frane_sh2_sfu_window(debug_get_num_option("TU_FRANE_SHADER_SFU_WINDOW", 6));''')
edit('vulkan/tu_device.cc', '      uint32_t options[12];',
     '      uint32_t options[15];')
edit('ir3/ir3_disk_cache.c', '         compiler->frane_sh1_threshold,',
     '''         compiler->frane_sh1_threshold,
         compiler->frane_sh2_critical,
         compiler->frane_sh2_sfu,
         compiler->frane_sh2_sfu_window,''')
for rel in ('vulkan/tu_device.cc', 'ir3/ir3_disk_cache.c'):
    edit(rel, 'frane-a810-v38-sh1-compile-options-v1',
         'frane-a810-v38-sh2-compile-options-v1')
edit('vulkan/tu_device.cc', 'Turnip-Drnas A810 V38 SH1 / Mesa ',
     'Turnip-Drnas A810 V38 SH2 / Mesa ')

after = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
         for p in root.rglob('*') if p.is_file()}
changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
assert changed == allowed, changed
print('SH2: shader-only scope and normalized cache identities verified')
