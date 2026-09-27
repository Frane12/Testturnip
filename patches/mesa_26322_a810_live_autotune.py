from pathlib import Path
p=Path('mesa/src/freedreno/vulkan/tu_autotune.cc');s=p.read_text()
def edit(a,b):
 global s
 assert s.count(a)==1,(a[:100],s.count(a))
 s=s.replace(a,b,1)
edit('static bool\nfrane_a810_gmem_turbo_enabled', '''static bool
frane_a810_live_profiled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26322_LIVE_AUTOTUNE", true);
   if (!enabled || !device || !device->physical_device)
      return false;
   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) || id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_gmem_turbo_enabled''')
edit('      std::atomic<uint32_t> measurement_ticket { 0 };','''      std::atomic<uint32_t> measurement_ticket { 0 };
      std::atomic<uint32_t> live_probe_ticket { 0 };''')
edit('         measurement_ticket.store((uint32_t)hash, std::memory_order_relaxed);','''         measurement_ticket.store((uint32_t)hash, std::memory_order_relaxed);
         live_probe_ticket.store((uint32_t)hash, std::memory_order_relaxed);''')
edit('''      void update(rp_history &history, bool immediate)
      {
         if (locked)
            return;''','''      void update(rp_history &history, bool immediate, bool live_profiled = false)
      {
         /* Only the explicit immediate/conformance mode may retain a permanent
          * lock on A810. State here is owned by the submit thread.
          */
         if (live_profiled && !immediate)
            locked = false;
         if (locked)
            return;''')
edit('''         if (!immediate && history.frane_cache_warmed &&''','''         if (live_profiled && !immediate) {
            sysmem_prob = std::clamp(sysmem_prob, 1u, 99u);
            sysmem_probability.store(sysmem_prob, std::memory_order_relaxed);
         }
         if (!immediate && history.frane_cache_warmed &&''')
edit('''               if (has_resolved && enough_samples && max_avg >= MIN_LOCK_THRESHOLD &&''','''               if (!live_profiled && has_resolved && enough_samples && max_avg >= MIN_LOCK_THRESHOLD &&''')
edit('''         bool gmem_turbo = false)
''','''         bool gmem_turbo = false,
         bool live_profiled = false)
''')
edit('''         const render_mode mode =
            select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;

         if (measure) {''','''         /* Bounded exploration for a strong winner: in every 128 strong
          * decisions measure the alternative once and the winner once.
          * Run AFTER SMART-GMEM so its promotion cannot swallow the probe.
          * Ordinary uncertain decisions keep their existing sampling.
          * Unsigned wrap is intentional; a power-of-two period preserves it.
          */
         if (live_profiled && (l_sysmem_probability <= 5 ||
                               l_sysmem_probability >= 95)) {
            const uint32_t phase =
               live_probe_ticket.fetch_add(1, std::memory_order_relaxed) & 127u;
            if (phase == 0 || phase == 64) {
               const bool preferred_sysmem = l_sysmem_probability >= 95;
               select_sysmem = phase == 0 ? !preferred_sysmem : preferred_sysmem;
               runtime_force_measure = true;
            }
         }

         const render_mode mode =
            select_sysmem ? render_mode::SYSMEM : render_mode::GMEM;

         if (measure) {''')
edit('''            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM));''','''            profiled.update(*this, at_config.is_enabled(algorithm::PROFILED_IMM),
                            frane_a810_live_profiled(at.device));''')
edit('''         frane_a810_gmem_turbo_enabled(device));''','''         frane_a810_gmem_turbo_enabled(device),
         frane_a810_live_profiled(device));''')
edit('''      return history.profiled.get_optimal_mode(history);''','''      return history.profiled.get_optimal_mode(
         history, nullptr, false, nullptr, false, false,
         config.is_enabled(algorithm::PROFILED) && frane_a810_live_profiled(device));''')
p.write_text(s)
p=Path('mesa/src/freedreno/vulkan/tu_device.cc');s=p.read_text();a='Frane Mesa 26.3.21 A810 TILE-COST EXP / Mesa ';assert s.count(a)==1;p.write_text(s.replace(a,'Frane Mesa 26.3.22 A810 LIVE-AUTOTUNE EXP / Mesa '))
print('26.3.22 A810 live autotune applied')
