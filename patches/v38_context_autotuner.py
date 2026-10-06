#!/usr/bin/env python3
"""V38 A810 context-aware AUTOTUNER experiment.

Applied strictly after the validated V38 GMEM-SEARCH stack.

Goals:
- keep V38 GMEM allocator/search and correctness gates unchanged;
- split PROFILED history only when coarse workload context materially changes;
- retain Mesa/V38 timing learning inside each context;
- reopen a strong learned preference after two >=20% faster control probes
  from the alternative mode;
- keep an A/B switch for exact V38 autotuner behavior.

A/B:
  TU_A810_V38_CONTEXT_AUTOTUNER=1 default
  TU_A810_V38_CONTEXT_AUTOTUNER=0 exact V38 autotuner identity/learning
"""
from pathlib import Path
import shutil

ROOT = Path("mesa/src/freedreno/vulkan")
SRC = ROOT / "tu_autotune.cc"
DEV = ROOT / "tu_device.cc"

def edit(path, old, new, label):
    p = Path(path)
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V38 AUTOTUNER source drift {label}: expected 1, got {n}")
    p.write_text(s.replace(old, new, 1))
    print(f"V38 AUTOTUNER PASS {label}", flush=True)

# Install the pure helper into the Mesa source tree.
shutil.copyfile(
    "patches/frane_v38_context_autotune.h",
    ROOT / "frane_v38_context_autotune.h",
)

edit(
    SRC,
    '#include "frane_mesa_26319_memory_audit.h"\n',
    '#include "frane_mesa_26319_memory_audit.h"\n'
    '#include "frane_v38_context_autotune.h"\n',
    "include context helper",
)

live_anchor = r'''static bool
frane_a810_live_profiled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26322_LIVE_AUTOTUNE", true);
   if (!enabled || !device || !device->physical_device)
      return false;
   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) || id == UINT64_C(0xffff44010000);
}
'''

live_new = live_anchor + r'''
static bool
frane_a810_v38_context_autotuner_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_V38_CONTEXT_AUTOTUNER", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}
'''

edit(SRC, live_anchor, live_new, "add A810 context-autotuner gate")

edit(
    SRC,
    r'''      std::atomic<uint32_t> measurement_ticket { 0 };
      std::atomic<uint32_t> live_probe_ticket { 0 };
      bool should_reset = false; /* If true, will reset sysmem_probability before next update. */
''',
    r'''      std::atomic<uint32_t> measurement_ticket { 0 };
      std::atomic<uint32_t> live_probe_ticket { 0 };
      uint8_t reversal_votes = 0;
      uint8_t reversal_direction = 0;
      bool should_reset = false; /* If true, will reset sysmem_probability before next update. */
''',
    "add reversal state",
)

update_anchor = r'''      void update(rp_history &history, bool immediate, bool live_profiled = false)
      {
'''

reversal = r'''      bool observe_context_reversal(rp_history &history,
                                    bool sample_is_sysmem,
                                    uint64_t duration,
                                    bool live_profiled)
      {
         if (!live_profiled || !duration)
            return false;

         const uint32_t probability =
            sysmem_probability.load(std::memory_order_relaxed);
         const uint64_t incumbent =
            sample_is_sysmem ? history.gmem_rp_average.get()
                             : history.sysmem_rp_average.get();

         const auto observation =
            frane_v38_reversal_vote(probability, sample_is_sysmem,
                                    duration, incumbent);

         if (observation == frane_v38_reversal_observation::IGNORE)
            return false;

         if (observation == frane_v38_reversal_observation::NONE) {
            reversal_votes = 0;
            reversal_direction = 0;
            return false;
         }

         const uint8_t direction = (uint8_t) observation;
         if (reversal_direction != direction) {
            reversal_direction = direction;
            reversal_votes = 1;
         } else if (reversal_votes < 2) {
            reversal_votes++;
         }

         if (reversal_votes < 2)
            return false;

         /* The old winner no longer describes this context. Recenter rather
          * than dragging stale long-term averages through the new phase.
          * Current control sample is retained as the first new observation.
          */
         history.sysmem_rp_average.clear();
         history.gmem_rp_average.clear();
         if (sample_is_sysmem)
            history.sysmem_rp_average.add(duration);
         else
            history.gmem_rp_average.add(duration);

         sysmem_probability.store(PROBABILITY_MID, std::memory_order_relaxed);
         locked = false;
         should_reset = false;
         winning_since_ts = 0;
         is_sysmem_winning = false;
         reversal_votes = 0;
         reversal_direction = 0;

         /* Also discard timing-derived GMEM promotion state so an old phase
          * cannot override the reopened profiler decision.
          */
         history.frane_gmem_runtime_state = {};
         history.frane_gmem_freshness = {};
         history.frane_gmem_runtime_word.store(0, std::memory_order_relaxed);
         history.frane_interval.store(1, std::memory_order_relaxed);
         history.frane_cache_warmed = false;
         history.frane_last_saved_probability = PROBABILITY_MID;

         return true;
      }

''' + update_anchor

edit(SRC, update_anchor, reversal, "add strong-winner reopen detector")

process_old = r'''         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM),
                            frane_a810_live_profiled(at.device));
            const uint64_t sys = sysmem_rp_average.get();
'''

process_new = r'''         if (at_config.is_enabled(algorithm::PROFILED) || at_config.is_enabled(algorithm::PROFILED_IMM)) {
            const bool live_profiled = frane_a810_live_profiled(at.device);
            const bool recentered =
               profiled.observe_context_reversal(
                  *this, entry.sysmem, rp_duration, live_profiled);

            if (!recentered) {
               profiled.update(*this,
                               at_config.is_enabled(algorithm::PROFILED_IMM),
                               live_profiled);
            } else if (frane_v28_universal_profiled(at.device)) {
               /* Do not resurrect a stale strong preference on the next run. */
               at.frane_save_profile(hash, 50);
               frane_last_cache_ns = os_time_get_nano();
            }

            const uint64_t sys = sysmem_rp_average.get();
'''

edit(SRC, process_old, process_new, "wire reopen detector into measured results")

key_old = r'''   rp_key key(0);
   if (key_opt)
      key = *key_opt;
   else
      key = cb_ctx.generate_rp_key(pass, framebuffer, cmd_buffer);

   rp_history_handle history_owner = find_or_create_rp_history(key);
'''

key_new = r'''   rp_key key(0);
   if (key_opt)
      key = *key_opt;
   else
      key = cb_ctx.generate_rp_key(pass, framebuffer, cmd_buffer);

   /* V38 AUTOTUNER: preserve Mesa's base RP identity, then split only
    * materially different A810 PROFILED contexts into separate histories.
    * This avoids mixing e.g. a light sky pass with a draw-dense/depth-heavy
    * use of the same framebuffer while keeping the bucket count bounded.
    */
   if (config.is_enabled(algorithm::PROFILED) &&
       !config.test(mod_flag::PREEMPT_OPTIMIZE) &&
       frane_a810_v38_context_autotuner_enabled(device)) {
      uint64_t pass_pixels = 0;
      if (cmd_state->per_layer_render_area) {
         for (unsigned i = 0; i < cmd_state->pass->num_views; i++) {
            const VkExtent2D &extent = cmd_state->render_areas[i].extent;
            pass_pixels += uint64_t(extent.width) * extent.height;
         }
      } else {
         const VkExtent2D &extent = cmd_state->render_areas[0].extent;
         pass_pixels = uint64_t(extent.width) * extent.height *
            MAX2(cmd_state->pass->num_views, cmd_state->framebuffer->layers);
      }

      bool has_depth = false;
      bool has_stencil = false;
      for (uint32_t i = 0; i < pass->attachment_count; i++) {
         const auto &att = pass->attachments[i];
         if (!att.gmem)
            continue;
         has_depth |= vk_format_has_depth(att.format);
         has_stencil |= vk_format_has_stencil(att.format);
      }

      const uint32_t draw_bw =
         rp_state->drawcall_count
            ? rp_state->drawcall_bandwidth_per_sample_sum /
                 rp_state->drawcall_count
            : 0;

      const frane_v38_context_input context = {
         .drawcalls = rp_state->drawcall_count,
         .pass_pixels = pass_pixels,
         .gmem_pixels = pass->gmem_pixels[TU_GMEM_LAYOUT_FULL],
         .sysmem_bandwidth_per_pixel = pass->sysmem_bandwidth_per_pixel,
         .gmem_bandwidth_per_pixel = pass->gmem_bandwidth_per_pixel,
         .draw_bandwidth_per_sample = draw_bw,
         .has_depth = has_depth,
         .has_stencil = has_stencil,
      };

      const uint32_t context_word = frane_v38_context_word(context);
      key.hash = XXH3_64bits_withSeed(
         &key.hash, sizeof(key.hash), (uint64_t) context_word);
   }

   rp_history_handle history_owner = find_or_create_rp_history(key);
'''

edit(SRC, key_old, key_new, "split PROFILED history by coarse render context")

edit(
    DEV,
    "Turnip A810 V38 / Mesa ",
    "Turnip A810 V38 AUTOTUNER / Mesa ",
    "experimental driver identity",
)

src = SRC.read_text()
dev = DEV.read_text()
hdr = (ROOT / "frane_v38_context_autotune.h").read_text()

for needle in (
    'TU_A810_V38_CONTEXT_AUTOTUNER", true',
    "frane_v38_context_word(context)",
    "XXH3_64bits_withSeed",
    "observe_context_reversal",
    "reversal_votes",
    "frane_v38_reversal_vote",
    "at.frane_save_profile(hash, 50)",
):
    assert needle in src, needle

for needle in (
    "frane_v38_context_input",
    "frane_v38_reversal_observation",
    "frane_v38_context_word",
):
    assert needle in hdr, needle

assert "Turnip A810 V38 AUTOTUNER / Mesa " in dev
assert 'TU_A810_26338_GMEM_SEARCH", true' in (ROOT / "tu_pass.cc").read_text()

print("V38 A810 context-aware AUTOTUNER applied", flush=True)
