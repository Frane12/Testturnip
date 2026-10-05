from pathlib import Path

ROOT=Path('mesa')
def edit(rel, old, new):
    p=ROOT/rel
    s=p.read_text()
    if s.count(old)!=1:
        raise SystemExit(f'S4 anchor mismatch: {rel}: {s.count(old)}: {old[:100]!r}')
    p.write_text(s.replace(old,new,1))

ir3='src/freedreno/ir3/'
(ROOT/ir3/'frane_s4_sched.h').write_bytes(Path('patches/frane_s4_sched.h').read_bytes())
edit(ir3+'ir3_sched.c', '#include "ir3.h"', '#include "ir3.h"\n#include "frane_s4_sched.h"')
edit(ir3+'ir3_compiler.h','   uint8_t frane_26317_tex_window_max;', '''   uint8_t frane_26317_tex_window_max;
   bool frane_s4_sched_window;
   bool frane_s4_sched_critical;
   bool frane_s4_sched_sfu;
   uint8_t frane_s4_sfu_max;
   uint8_t frane_s4_sched_slack;''')
edit(ir3+'ir3_compiler.c', 'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 4)', 'debug_get_num_option("TU_A810_26317_TEX_WINDOW_MAX", 6)')
edit(ir3+'ir3_compiler.c', '         (unsigned)CLAMP(frane_tex_window, 2, 8);', '''         (unsigned)CLAMP(frane_tex_window, 2, 8);
      compiler->frane_s4_sched_window = debug_get_bool_option("TU_FRANE_SCHED_WINDOW", true);
      compiler->frane_s4_sched_critical = debug_get_bool_option("TU_FRANE_SCHED_CRITICAL", true);
      compiler->frane_s4_sched_sfu = debug_get_bool_option("TU_FRANE_SCHED_SFU", true);
      compiler->frane_s4_sfu_max = CLAMP(debug_get_num_option("TU_FRANE_SFU_WINDOW", 6), 2, 8);
      compiler->frane_s4_sched_slack = CLAMP(debug_get_num_option("TU_FRANE_SCHED_SLACK", 2), 0, 4);''')
edit(ir3+'ir3_disk_cache.c', '         compiler->frane_26317_tex_window_max,', '''         compiler->frane_26317_tex_window_max,
         compiler->frane_s4_sched_window,
         compiler->frane_s4_sched_critical,
         compiler->frane_s4_sched_sfu,
         compiler->frane_s4_sfu_max,
         compiler->frane_s4_sched_slack,''')
edit(ir3+'ir3_disk_cache.c','frane-a810-compile-options-v1','frane-a810-compile-options-v2')
edit(ir3+'ir3_sched.c','   const unsigned max_window = ctx->compiler->frane_26317_tex_window_max;', '''   const unsigned max_window = ctx->compiler->frane_26317_tex_window_max;
   if (ctx->compiler->frane_s4_sched_window)
      return frane_s4_window(p, max_window, false);''')
edit(ir3+'ir3_sched.c','   if (ctx->ss_index - ctx->first_outstanding_ss_index >= 8 && is_ss_producer(instr))', '''   const unsigned ss_window = ctx->compiler->frane_26317_adaptive_sched &&
      ctx->compiler->frane_s4_sched_sfu ?
      frane_s4_window(frane_26317_pressure_pct(ctx),
                      ctx->compiler->frane_s4_sfu_max, true) : 8;
   if ((unsigned)(ctx->ss_index - ctx->first_outstanding_ss_index) >= ss_window && is_ss_producer(instr))''')
edit(ir3+'ir3_sched.c', '   int chosen_live_growth = 0;', '''   int chosen_live_growth = 0;
   int64_t chosen_score = INT64_MIN;
   const bool critical = ctx->compiler->frane_26317_adaptive_sched &&
      ctx->compiler->frane_s4_sched_critical;
   const unsigned pressure = frane_26317_pressure_pct(ctx);''')
edit(ir3+'ir3_sched.c', '''      int live_growth = ctx->compiler->frane_26317_adaptive_sched ?
         live_effect(n->instr) : 0;''', '''      int live_growth = ctx->compiler->frane_26317_adaptive_sched ?
         live_effect(n->instr) : 0;
      const int64_t score = frane_s4_score(pressure, live_growth, distance,
                                         n->max_delay,
                                         ctx->compiler->frane_s4_sched_slack);''')
edit(ir3+'ir3_sched.c', '''      if (!better && rank == chosen_rank) {
         if (ctx->compiler->frane_26317_adaptive_sched &&
             live_growth < chosen_live_growth)''', '''      if (!better && rank == chosen_rank) {
         if (critical) {
            better = score > chosen_score;
         } else if (ctx->compiler->frane_26317_adaptive_sched &&
             live_growth < chosen_live_growth)''')
edit(ir3+'ir3_sched.c', '         chosen_live_growth = live_growth;', '         chosen_live_growth = live_growth;\n         chosen_score = score;')

p='src/freedreno/vulkan/tu_pass.cc'
edit(p,'   bool future_pressure;', '''   bool future_pressure;
   uint32_t peak_upper;''')
helpers=Path('patches/frane_s4_gmem.inc').read_text()
edit(p, 'struct frane_gmem_search_option {', helpers+'\nstruct frane_gmem_search_option {')
edit(p, '   if (++ctx->nodes > ctx->node_budget)', '   if (ctx->best_pixels >= ctx->peak_upper || ++ctx->nodes > ctx->node_budget)')
edit(p, '''   uint32_t budget = budget_opt < 128 ? 128u : (uint32_t) budget_opt;''', '''   budget_opt = debug_get_num_option("TU_FRANE_GMEM_BUDGET", 16384);
   uint32_t budget = budget_opt < 128 ? 128u : (uint32_t) budget_opt;''')
edit(p, '      .future_pressure = future_pressure,', '      .future_pressure = future_pressure,\n      .peak_upper = UINT32_MAX,')
edit(p, '   frane_gmem_search_recurse(&ctx, 0, tracks, 0);', '''   if (debug_get_bool_option("TU_FRANE_GMEM_PEAK_BOUND", true))
      ctx.peak_upper = frane_s4_peak_upper(&ctx);
   if (debug_get_bool_option("TU_FRANE_GMEM_MULTISEED", true))
      frane_s4_multiseed(&ctx,
         CLAMP(debug_get_num_option("TU_FRANE_GMEM_SEEDS", 4), 1, 4),
         debug_get_bool_option("TU_FRANE_GMEM_GAPS", true));
   frane_gmem_search_recurse(&ctx, 0, tracks, 0);''')
edit('src/freedreno/vulkan/tu_device.cc', 'A810 S3 Orchestrator / Mesa ', 'A810 S4 Max / Mesa ')
print('S4 Max applied: multi-start GMEM, peak bound, gap fit, pressure windows, critical path, SFU window')
