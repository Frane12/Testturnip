#!/usr/bin/env python3
"""Overlay S1 AT2 hysteresis on an ALREADY-applied S1 AT1 Mesa source tree.

Run after patches/s1_at1_contextual_autotune.py, before Meson.
Source-drift checks fail closed. This is a draft, not a driver binary.
"""
from pathlib import Path
import shutil

ROOT = Path('mesa')
V = ROOT / 'src/freedreno/vulkan'


def edit(rel, old, new, label):
    path = ROOT / rel
    text = path.read_text()
    found = text.count(old)
    if found != 1:
        raise SystemExit(f'AT2 source drift at {label}: expected one anchor, got {found}')
    path.write_text(text.replace(old, new, 1))
    print('AT2 patched:', label, flush=True)


if not (V / 'frane_s1at1_contextual_autotune.h').exists():
    raise SystemExit('Apply S1 AT1 patch FIRST, then the AT2 overlay')
if (V / 'frane_s1at2_hysteresis.h').exists():
    raise SystemExit('AT2 header already installed; refusing duplicate patch')

shutil.copyfile('patches/frane_s1at2_hysteresis.h',
                V / 'frane_s1at2_hysteresis.h')

edit('src/freedreno/vulkan/tu_autotune.cc',
     '#include "frane_s1at1_contextual_autotune.h"',
     '#include "frane_s1at1_contextual_autotune.h"\n'
     '#include "frane_s1at2_hysteresis.h"',
     'include AT2 policy')

edit('src/freedreno/vulkan/tu_autotune.cc',
     '''static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{''',
     '''static bool
frane_a810_s1at2_enabled(const struct tu_device *device)
{
   /* AT2 is a strictly optional overlay and cannot outlive AT1. */
   static const bool enabled = debug_get_bool_option("TU_FRANE_AT2", true);
   return enabled && frane_a810_s1at1_enabled(device);
}

static bool
frane_a810_tail_signature_enabled(const struct tu_device *device)
{''',
     'add AT2 gated opt-in and AT1 rollback')

edit('src/freedreno/vulkan/tu_autotune.cc',
     'std::atomic<uint32_t> frane_s1at1_word { 16u };',
     '''std::atomic<uint32_t> frane_s1at1_word { 16u };

   /* AT2 submit-thread state and recording-thread read-only snapshot. */
   frane_s1at2_state frane_s1at2_state_data {};
   std::atomic<uint32_t> frane_s1at2_word { 0u };''',
     'add per-render-pass AT2 history')

edit('src/freedreno/vulkan/tu_autotune.cc',
     '''            frane_s1at1_word.store(
               frane_s1at1_pack_snapshot(frane_s1at1_state_data),
               std::memory_order_relaxed);
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {''',
     '''            frane_s1at1_word.store(
               frane_s1at1_pack_snapshot(frane_s1at1_state_data),
               std::memory_order_relaxed);

            if (frane_a810_s1at2_enabled(at.device)) {
               frane_s1at2_state_data = frane_s1at2_update_state(
                  frane_s1at2_state_data,
                  frane_s1at1_state_data.score,
                  frane_s1at1_state_data.volatility,
                  entry.frane_s1at1_signature,
                  frane_s1at1_state_data.sysmem.samples,
                  frane_s1at1_state_data.gmem.samples);
               frane_s1at2_word.store(
                  frane_s1at2_pack(frane_s1at2_state_data),
                  std::memory_order_relaxed);
            }
         }

         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {''',
     'update AT2 ONLY after measured AT1 GPU pass timing')

edit('src/freedreno/vulkan/tu_autotune.cc',
     '''         bool s1at1_context = false)
      {''',
     '''         bool s1at1_context = false,
         bool s1at2_context = false)
      {''',
     'carry separate AT2 gate to PROFILED mode selection')

edit('src/freedreno/vulkan/tu_autotune.cc',
     '''               const auto at1 = frane_s1at1_decide(
                  true, at1_in, at1_snapshot, decision_word);
               if (at1.override_mode) {
                  runtime_decision.override_mode = true;
                  runtime_decision.select_sysmem = at1.select_sysmem;
                  runtime_decision.force_measure = at1.force_measure;
               }''',
     '''               const auto at1 = frane_s1at1_decide(
                  true, at1_in, at1_snapshot, decision_word);
               bool select_sysmem = at1.select_sysmem;

               if (s1at2_context && at1.override_mode) {
                  frane_s1at2_input at2_in {};
                  at2_in.at1_override = at1.override_mode;
                  at2_in.at1_select_sysmem = at1.select_sysmem;
                  at2_in.at1_force_measure = at1.force_measure;
                  at2_in.at1_effective_sysmem_probability =
                     at1.effective_sysmem_probability;
                  at2_in.signature = at1.signature;
                  at2_in.decision_word = decision_word;
                  at2_in.learned = frane_s1at2_unpack(
                     history.frane_s1at2_word.load(std::memory_order_relaxed));
                  select_sysmem = frane_s1at2_decide(at2_in).select_sysmem;
               }

               if (at1.override_mode) {
                  runtime_decision.override_mode = true;
                  runtime_decision.select_sysmem = select_sysmem;
                  runtime_decision.force_measure = at1.force_measure;
               }''',
     'add bounded hysteresis overlay without touching AT1 probes')

edit('src/freedreno/vulkan/tu_autotune.cc',
     '''         frane_a810_live_profiled(device),
         frane_a810_s1at1_enabled(device));''',
     '''         frane_a810_live_profiled(device),
         frane_a810_s1at1_enabled(device),
         frane_a810_s1at2_enabled(device));''',
     'enable AT2 when supported on Adreno 810')

edit('src/freedreno/vulkan/tu_device.cc',
     'Drnas-Turnip S1 AT1 A810 / Mesa ',
     'Drnas-Turnip S1 AT2 A810 / Mesa ',
     'set draft build display name')

source = (V / 'tu_autotune.cc').read_text()
for token in ('TU_FRANE_AT1", true', 'TU_FRANE_AT2", true',
              'frane_s1at1_update_state', 'frane_s1at2_update_state',
              'frane_s1at2_decide', 'frane_s1at2_word',
              'frane_a810_live_profiled(device)', 'locked = false;'):
    assert token in source, token
print('S1 AT2 hysteresis draft source patch complete', flush=True)
