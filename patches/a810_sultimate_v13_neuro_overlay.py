#!/usr/bin/env python3
"""v1.3 Neuro Shadow — integrate asynchronous GPU feedback into rp_history.
This patch is strictly observational: NEVER changes GMEM/SYSMEM decisions.
Apply AFTER v1.2 S1BP overlay and the complete v1.1 safety fixes.
"""
from pathlib import Path
import shutil
V=Path("mesa/src/freedreno/vulkan")
auto=V/"tu_autotune.cc"
dev=V/"tu_device.cc"
bph=V/"frane_a810_s1_bandwidth_probe.h"
shutil.copyfile("patches/frane_s1_neuro_shadow.h",V/"frane_s1_neuro_shadow.h")
def change(path,old,new,label):
  s=path.read_text()
  count=s.count(old)
  if count!=1:
    raise SystemExit(f"S1 NEURO SOURCE DRIFT {label}: {count}")
  path.write_text(s.replace(old,new,1))
  print("S1 NEURO PASS",label,flush=True)

change(auto,
'#include "frane_a810_s1_bandwidth_probe.h"',
'#include "frane_a810_s1_bandwidth_probe.h"\n#include "frane_s1_neuro_shadow.h"',
"include shadow")
change(auto,
'   std::atomic<uint32_t> frane_atu_v3_epoch { 0 };',
'''   std::atomic<uint32_t> frane_atu_v3_epoch { 0 };
   /* Per render-pass history: no learning shared across RP hashes. */
   frane_s1_neuro::Bank frane_s1_neuro_net {};
   std::atomic<uint64_t> frane_s1_neuro_serial { 0 };''',
"per-RP adaptive state")
change(auto,
'''         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM),''',
'''         /* Train ONLY on already completed GPU timestamped passes. The
          * entry carries its original signature from the command recording
          * thread; never join measurements using the current scene.
          * Serial is per RP history.  No new GPU queries or waits.
          */
         static const bool s1_neuro_train_on =
            debug_get_bool_option("TU_FRANE_S1_NEURO_SHADOW", true);
         if (s1_neuro_train_on && frane_a810_s1at3_enabled(at.device) &&
             entry.frane_s1at1_signature) {
            const uint64_t s1_serial =
               frane_s1_neuro_serial.fetch_add(
                  1, std::memory_order_relaxed) + 1;
            const auto s1_feat = frane_s1_neuro::from_signature(
               entry.frane_s1at1_signature);
            const frane_s1_neuro::Sample sample {
               s1_feat,
               entry.sysmem ? frane_s1_neuro::SYS : frane_s1_neuro::GMEM,
               rp_duration, s1_serial
            };
            frane_s1_neuro_net.train(sample);
         }
         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM),''',
"GPU completion training; per-entry signature")
change(auto,
'''         bp.at3_noise_q8 = snap.signature == cat.signature ?
            snap.at7_noise_q8 : 0;
         bp.final_source =''',
'''         bp.at3_noise_q8 = snap.signature == cat.signature ?
            snap.at7_noise_q8 : 0;
         /* Five tiny fixed-point operations and four atomic reads; this
          * prediction is only logged and cannot select a Vulkan render mode.
          */
         static const bool s1_neuro_shadow_on =
            debug_get_bool_option("TU_FRANE_S1_NEURO_SHADOW", true);
         if (s1_neuro_shadow_on) {
            const frane_s1_neuro::Gate gate {
               ev.eligible && context_eligible,
               frane_a810_gmem_pass_safe(
                  device, cmd_state, pass, framebuffer),
               at3_controlled && measure,
               at3_controlled && measure,
               s1_runtime_override,
               depth_overrode
            };
            const auto prediction = history.frane_s1_neuro_net.infer(
               frane_s1_neuro::from_signature(cat.signature),gate);
            bp.neuro_trusted = prediction.trusted;
            bp.neuro_sysmem = prediction.preferred == frane_s1_neuro::SYS;
            bp.neuro_score = prediction.score;
            bp.neuro_votes = prediction.stable_votes;
            bp.neuro_agrees = prediction.trusted &&
               bp.neuro_sysmem == bp.final_sysmem;
         }
         bp.final_source =''',
"record gated shadow prediction alongside final GPU choice")
change(bph,
'''   const char *final_source = "UNKNOWN";
};''',
'''   const char *final_source = "UNKNOWN";
   bool neuro_trusted = false, neuro_sysmem = false, neuro_agrees = false;
   int neuro_score = 0;
   uint8_t neuro_votes = 0;
};''',
"append shadow fields to trace struct")
change(bph,
'''at3_score,at3_pairs,at3_noise_q8\\n",file);''',
'''at3_score,at3_pairs,at3_noise_q8,neuro_trusted,neuro_sysmem,neuro_score,neuro_votes,neuro_agrees\\n",file);''',
"append 5 CSV headers")
change(bph,
'''"2,%llu,%016llx,%llu,%llu,%u,%u,%u,%llu,%llu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%s,%s,%u,%u,%u,%d,%u,%u\\n",''',
'''"2,%llu,%016llx,%llu,%llu,%u,%u,%u,%llu,%llu,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%s,%s,%u,%u,%u,%d,%u,%u,%u,%u,%d,%u,%u\\n",''',
"append CSV formats")
change(bph,
'''         r.at3_score,r.at3_pairs,r.at3_noise_q8);''',
'''         r.at3_score,r.at3_pairs,r.at3_noise_q8,
         unsigned(r.neuro_trusted),unsigned(r.neuro_sysmem),
         r.neuro_score,unsigned(r.neuro_votes),unsigned(r.neuro_agrees));''',
"append 5 CSV fields")
change(dev,'Drnas-Turnip A810 S Ultimate v1.2 / Mesa ',
       'Drnas-Turnip A810 S Ultimate v1.3 / Mesa ',
       "driverInfo")
change(dev,'"Drnas-Turnip A810 S Ultimate v1.2" : pdevice->name',
       '"Drnas-Turnip A810 S Ultimate v1.3" : pdevice->name',
       "HUD adapter label")
print("S1 Neuro Shadow v1.3 — GPU callback to atomic shadow inference PASS")
