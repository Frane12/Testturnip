from pathlib import Path

ROOT = Path('mesa')
V = ROOT / 'src/freedreno/vulkan'

def edit(rel, old, new):
    p = ROOT / rel
    s = p.read_text()
    if s.count(old) != 1:
        raise SystemExit(f'S3 anchor mismatch: {rel}: {s.count(old)}: {old[:100]!r}')
    p.write_text(s.replace(old, new, 1))

(V / 'frane_s3_orchestrator.h').write_bytes(Path('patches/frane_s3_orchestrator.h').read_bytes())
autotune = 'src/freedreno/vulkan/tu_autotune.cc'
edit(autotune, '#include "frane_mesa_26364_a810_smart_v2.h"',
     '#include "frane_mesa_26364_a810_smart_v2.h"\n#include "frane_s3_orchestrator.h"')
loader = '''static const frane_s3_config &
frane_s3_options()
{
   static const frane_s3_config cfg = [] {
      auto read = [](const char *name, int64_t def, int64_t low, int64_t high) {
         return uint32_t(std::clamp<int64_t>(debug_get_num_option(name, def), low, high));
      };
      frane_s3_config c {};
      c.enabled = debug_get_bool_option("TU_FRANE_ORCH", true);
      c.policy = read("TU_FRANE_ORCH_POLICY", 1, 0, 3);
      if (c.policy == 2) {
         c.hot_log2=10; c.sentinel_log2=9; c.min_pairs=4; c.gain=15; c.risk=50;
      } else if (c.policy == 3) {
         c.cold_log2=3; c.hot_log2=8; c.sentinel_log2=6;
         c.min_pairs=8; c.gain=40; c.risk=150;
      }
      c.cold_log2=read("TU_FRANE_ORCH_COLD_LOG2",c.cold_log2,3,6);
      c.warm_log2=read("TU_FRANE_ORCH_WARM_LOG2",c.warm_log2,3,9);
      c.hot_log2=read("TU_FRANE_ORCH_HOT_LOG2",c.hot_log2,3,10);
      c.sentinel_log2=read("TU_FRANE_ORCH_SENTINEL_LOG2",c.sentinel_log2,4,10);
      c.min_pairs=read("TU_FRANE_ORCH_MIN_PAIRS",c.min_pairs,4,16);
      c.gain=read("TU_FRANE_ORCH_GAIN",c.gain,5,250);
      c.risk=read("TU_FRANE_ORCH_RISK",c.risk,0,400);
      c.ema_shift=read("TU_FRANE_ORCH_EMA_SHIFT",c.ema_shift,1,5);
      c.drift=read("TU_FRANE_ORCH_DRIFT",c.drift,100,1000);
      c.drift_hits=read("TU_FRANE_ORCH_DRIFT_HITS",c.drift_hits,1,4);
      c.max_age=read("TU_FRANE_ORCH_MAX_AGE",c.max_age,16,65536);
      c.max_tiles=read("TU_FRANE_ORCH_MAX_TILES",c.max_tiles,8,128);
      c.min_ticks=(read("TU_FRANE_ORCH_MIN_US",8,0,1000)*192+5)/10;
      return frane_s3_normalize(c);
   }();
   return cfg;
}

'''
edit(autotune, 'static bool\nfrane_a810_histogram_log_enabled',
     loader+'static bool\nfrane_a810_histogram_log_enabled')
edit(autotune, '   bool frane_smart_sample = false;',
     '''   bool frane_smart_sample = false;
   bool frane_orch_sample = false;
   bool frane_orch_paired = false;
   uint32_t frane_orch_tag = 0;''')
edit(autotune, '   std::atomic<uint64_t> frane_smart_word { 0 };',
     '''   std::atomic<uint64_t> frane_smart_word { 0 };
   frane_s3_state frane_orch_state {};
   std::atomic<uint64_t> frane_orch_word { 0 };''')
edit(autotune, '         bool live_profiled = false)\n      {',
     '         bool live_profiled = false,\n         frane_s3_decision *orch_decision = nullptr)\n      {')
edit(autotune, '         frane_26318_smart_gmem_input cold_input {};',
     '''         const auto &orch_cfg = frane_s3_options();
         if (measure && lean_fastpath && gmem_turbo && gmem_runtime_input &&
             gmem_runtime_input->hist_smooth && orch_cfg.enabled && orch_cfg.policy &&
             frane_s3_eligible(gmem_runtime_input->layout, orch_cfg)) {
            const auto &in = *gmem_runtime_input;
            const auto d = frane_s3_select(orch_cfg,
               in.zs_load_store || in.layout.pass_pixels>=UINT64_C(2073600),
               history.frane_orch_word.load(std::memory_order_relaxed),
               l_sysmem_probability, in.tail_occurrences, history.hash);
            if (d.owns) {
               if (orch_decision) *orch_decision=d;
               *measure=d.measure;
               return d.sysmem ? render_mode::SYSMEM : render_mode::GMEM;
            }
         }
         frane_26318_smart_gmem_input cold_input {};''')
edit(autotune, '         if (entry.frane_smart_sample &&\n',
     '''         if (entry.frane_orch_sample) {
            const uint64_t before=frane_s3_pack(frane_orch_state,frane_s3_options());
            frane_s3_feed(frane_orch_state,frane_s3_options(),entry.sysmem,
               rp_duration,entry.frane_smart_occurrence,
               entry.frane_orch_paired,entry.frane_orch_tag);
            const uint64_t after=frane_s3_pack(frane_orch_state,frane_s3_options());
            frane_orch_word.store(after,std::memory_order_relaxed);
            static const bool log=debug_get_bool_option("TU_FRANE_ORCH_LOG",false);
            if (unlikely(log) && (((before^after)&31) ||
                (entry.frane_orch_paired && !(frane_orch_state.pairs&15)))) {
               mesa_logi("DRNAS_ORCH rp=%016" PRIx64
                  " pairs=%u pref=%c trusted=%u gain=%d mad=%d resets=%u",
                  hash,frane_orch_state.pairs,frane_orch_state.sysmem?'S':'G',
                  unsigned(frane_orch_state.trusted),frane_orch_state.mean,
                  frane_orch_state.deviation,frane_orch_state.resets);
            }
         }
         if (!entry.frane_orch_sample && entry.frane_smart_sample &&
''')
edit(autotune, '         if (frane_a810_tail_learner_enabled(at.device)) {',
     '''         if (entry.frane_orch_sample) {
            if (at_config.is_enabled(algorithm::PROFILED) ||
                at_config.is_enabled(algorithm::PROFILED_IMM))
               profiled.update(*this,at_config.is_enabled(algorithm::PROFILED_IMM),
                               frane_a810_live_profiled(at.device));
            return;
         }
         if (frane_a810_tail_learner_enabled(at.device)) {''')
edit(autotune, '      render_mode mode = history.profiled.get_optimal_mode(\n         history, &measure,',
     '      frane_s3_decision orch_decision {};\n      render_mode mode = history.profiled.get_optimal_mode(\n         history, &measure,')
edit(autotune, '         frane_a810_live_profiled(device));\n\n      mode = frane_26350_depth_frontier',
     '         frane_a810_live_profiled(device), &orch_decision);\n\n      mode = frane_26350_depth_frontier')
edit(autotune, '         (*rp_ctx)->frane_smart_sample = runtime_input.hist_smooth;',
     '''         (*rp_ctx)->frane_orch_sample = orch_decision.owns;
         (*rp_ctx)->frane_orch_paired = orch_decision.paired;
         (*rp_ctx)->frane_orch_tag = orch_decision.tag;
         (*rp_ctx)->frane_smart_sample = runtime_input.hist_smooth && !orch_decision.owns;''')
edit(autotune, '         runtime_input.tail_guard =\n',
     '''         const bool orch_active = frane_s3_options().enabled &&
            frane_s3_options().policy && frane_a810_gmem_turbo_enabled(device) &&
            frane_a810_histogram_smooth_enabled(device) &&
            frane_s3_eligible(runtime_input.layout,frane_s3_options());
         runtime_input.tail_guard =
''')
for field in ('frane_tail_word','frane_tail_scan_word'):
    edit(autotune, f'            history.{field}.load(std::memory_order_relaxed);',
         f'            orch_active ? 0 : history.{field}.load(std::memory_order_relaxed);')
edit(autotune, '         if (runtime_input.hist_smooth) {',
     '         if (runtime_input.hist_smooth && !orch_active) {')
edit('src/freedreno/vulkan/tu_device.cc', 'A810 S2.1 Render Recovery / Mesa ',
     'Turnip-Drnas A810 S3 Orchestrator / Mesa ')

compiler='src/freedreno/ir3/ir3_compiler.c'
aliases={
   'TU_A810_26310_UBO_GAP':('TU_FRANE_UBO_GAP','64','num'),
   'TU_A810_26311_SAFE_TEX_PREFETCH':('TU_FRANE_TEX_PREFETCH','true','bool'),
   'TU_A810_26312_DUAL_TEX_PREFETCH':('TU_FRANE_PREFETCH_DUAL','true','bool'),
   'TU_A810_26314_TRIPLE_TEX_PREFETCH':('TU_FRANE_PREFETCH_TRIPLE','true','bool'),
   'TU_A810_26315_QUAD_TEX_PREFETCH':('TU_FRANE_PREFETCH_QUAD','true','bool'),
   'TU_A810_26315_PREFETCH_DIVERSITY':('TU_FRANE_PREFETCH_DIVERSITY','true','bool'),
   'TU_A810_26316_PREFETCH_USE_SCORE':('TU_FRANE_PREFETCH_SCORE','false','bool'),
   'TU_A810_26317_ADAPTIVE_SCHED':('TU_FRANE_SCHED','true','bool'),
   'TU_A810_26317_TEX_WINDOW_MAX':('TU_FRANE_TEX_WINDOW','4','num')
}
for old,(new,default,kind) in aliases.items():
    expr=f'debug_get_{kind}_option("{old}", {default})'
    edit(compiler,expr,f'debug_get_{kind}_option("{new}", {expr})')
edit(compiler, '      unsigned frane_tex_window =', '      int64_t frane_tex_window =')
edit(compiler, '         MIN2(8u, MAX2(2u, frane_tex_window));',
     '         (unsigned)CLAMP(frane_tex_window, 2, 8);')

cmd='src/freedreno/vulkan/tu_cmd_buffer.cc'
edit(cmd,'   return (unsigned)CLAMP(threshold, 4, 16);',
     '''   static const int bias=CLAMP(debug_get_num_option("TU_FRANE_CB_BIAS",0),-4,8);
   return (unsigned)CLAMP(threshold+bias,4,24);''')
edit(cmd,'   case 4:\n      /* Legacy broad pressure policy',
     '''   case 5: {
      static const uint32_t draws_min=CLAMP(debug_get_num_option("TU_FRANE_CB_KEEP_DRAWS",28),16,128);
      static const uint32_t tiles_min=CLAMP(debug_get_num_option("TU_FRANE_CB_KEEP_TILES",12),4,64);
      static const uint32_t bw_min=CLAMP(debug_get_num_option("TU_FRANE_CB_KEEP_BW",16),8,64);
      keep=draws>=draws_min && tile_count>=tiles_min && avg_bw>=bw_min;
      break;
   }
   case 4:
      /* Legacy broad pressure policy''')

print('S3 Orchestrator applied: one decision/measurement owner, paired feedback, drift probes, bounded controls')
