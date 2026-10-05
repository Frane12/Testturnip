#!/usr/bin/env python3
"""A810 S1 Smart CB1.

Layered on the frozen A810 S1 Smart Performance 2 patch stack.

Goal:
- keep Mesa/Turnip concurrent-binning correctness and synchronization intact;
- enable A810 CB only on structurally useful GMEM passes;
- let Turnip's existing GPU-side BV/BR feedback handle ordinary admitted passes;
- bypass that feedback only for a narrow upper envelope where overlap is very
  likely to amortize setup;
- avoid the broad additive CB-pressure policy that previously hurt warm-run
  throughput.

User-facing master:
  TU_FRANE_SMART_CB=1  (default)
  TU_FRANE_SMART_CB=0  (disable A810 smart CB override)

Optional experiment selector:
  TU_FRANE_SMART_CB_MODE=0  runtime feedback only, never keep CB forced
  TU_FRANE_SMART_CB_MODE=1  Smart CB1 conservative keep policy (default)
  TU_FRANE_SMART_CB_MODE=2  legacy V45 keep policy
  TU_FRANE_SMART_CB_MODE=3  balanced strict gate
  TU_FRANE_SMART_CB_MODE=4  legacy V46 pressure policy (reference only)

TU_DEBUG=nocb remains authoritative. TU_DEBUG=forcecb remains authoritative.
"""

from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"SMART-CB1 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:220]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"SMART-CB1 PASS {label}", flush=True)


edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    r'''static inline bool
frane_26344_a810_cb_override(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26344_SMART_CB", true);

   /* An explicit nocb request must remain authoritative. */
   return enabled &&
          !TU_DEBUG(NO_CONCURRENT_BINNING) &&
          frane_26344_is_a810(cmd);
}
''',
    r'''static inline bool
frane_26344_a810_cb_override(const struct tu_cmd_buffer *cmd)
{
   /* S1 Smart CB1 master. Keep TU_DEBUG=nocb authoritative and do not widen
    * the experiment to non-A810 chips.
    */
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_SMART_CB", true);

   return enabled &&
          !TU_DEBUG(NO_CONCURRENT_BINNING) &&
          frane_26344_is_a810(cmd);
}
''',
    "single Smart-CB master switch",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    r'''static inline unsigned
frane_26345_cb_min_draws(const struct tu_cmd_buffer *cmd,
                         uint32_t tile_count,
                         bool gmem_path)
{
   static const int base =
      MAX2(1, debug_get_num_option("TU_A810_26345_CB_BASE_DRAWS", 8));

   int threshold = base;

   if (!gmem_path) {
      /* Turnip explicitly notes that CB setup can regress sysmem workloads
       * with many short renderpasses, so stay conservative there.
       */
      threshold += 8;
   } else {
      /* More GMEM tiles mean more BR work is available to overlap with BV. */
      if (tile_count >= 16)
         threshold -= 4;
      else if (tile_count >= 8)
         threshold -= 3;
      else if (tile_count >= 4)
         threshold -= 1;
      else
         threshold += 2;

      const uint32_t avg_bw = frane_26345_avg_draw_bw(cmd);

      /* Heavier attachment traffic tends to give BR more useful work to hide
       * behind binning; very light passes need more draws to amortize setup.
       */
      if (avg_bw >= 24)
         threshold -= 2;
      else if (avg_bw && avg_bw <= 8)
         threshold += 1;
   }

   return (unsigned)CLAMP(threshold, 2, 24);
}
''',
    r'''static inline unsigned
frane_26345_cb_min_draws(const struct tu_cmd_buffer *cmd,
                         uint32_t tile_count,
                         bool gmem_path)
{
   /* Smart CB1 deliberately has separate admission and keep thresholds.
    * Admission is cheap and moderately permissive; the GPU-side BR/BV check
    * remains enabled for normal passes, so a mediocre admission does not turn
    * into a permanently forced CB decision.
    */
   if (!gmem_path)
      return 32;

   int threshold = 8;

   if (tile_count >= 16)
      threshold = 5;
   else if (tile_count >= 8)
      threshold = 6;
   else if (tile_count >= 4)
      threshold = 8;
   else if (tile_count >= 2)
      threshold = 10;
   else
      threshold = 14;

   const uint32_t avg_bw = frane_26345_avg_draw_bw(cmd);

   /* Strong BR work lowers the admission cost slightly. Very light attachment
    * traffic raises it, because BV vertex-fetch cost is then harder to hide.
    */
   if (avg_bw >= 32)
      threshold -= 1;
   else if (avg_bw && avg_bw <= 8)
      threshold += 2;

   return (unsigned)CLAMP(threshold, 4, 16);
}
''',
    "Smart-CB GMEM admission threshold",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    r'''static inline bool
frane_26345_cb_policy_allows(const struct tu_cmd_buffer *cmd,
                             uint32_t tile_count,
                             bool gmem_path)
{
   /* Explicit Mesa/DRI policy remains authoritative. */
   if (cmd->device->instance->drirc.perf.allow_concurrent_binning)
      return true;

   static const bool adaptive =
      debug_get_bool_option("TU_A810_26345_ADAPTIVE_CB", true);

   if (!adaptive)
      return frane_26344_cb_policy_allows(cmd);

   if (!frane_26344_a810_cb_override(cmd))
      return false;

   return cmd->state.rp.drawcall_count >=
          frane_26345_cb_min_draws(cmd, tile_count, gmem_path);
}
''',
    r'''static inline bool
frane_26345_cb_policy_allows(const struct tu_cmd_buffer *cmd,
                             uint32_t tile_count,
                             bool gmem_path)
{
   /* Explicit Mesa/DRI policy remains authoritative. */
   if (cmd->device->instance->drirc.perf.allow_concurrent_binning)
      return true;

   if (!frane_26344_a810_cb_override(cmd))
      return false;

   /* Upstream's known weak case is short desktop-style work where BV setup /
    * vertex fetch cannot be hidden. The A810 override therefore does not
    * admit SYSMEM at all; explicit Mesa/DRI enable above can still do so.
    */
   if (!gmem_path)
      return false;

   const uint32_t draws = cmd->state.rp.drawcall_count;
   if (draws < 4 || tile_count == 0)
      return false;

   return draws >= frane_26345_cb_min_draws(cmd, tile_count, true);
}
''',
    "Smart-CB admission policy",
)

start = r'''static inline bool
frane_26347_keep_cb_profile_policy(const struct tu_cmd_buffer *cmd,
                                   uint32_t tile_count,
                                   bool gmem_path)
{
   if (!gmem_path || !frane_26344_a810_cb_override(cmd))
      return false;

   static const unsigned mode =
      debug_get_num_option("TU_FRANE_CB_MODE", 1);

   const uint32_t draws = cmd->state.rp.drawcall_count;
   const uint32_t avg_bw = frane_26345_avg_draw_bw(cmd);
   const bool v45_keep = frane_26345_keep_cb_heavy(cmd, tile_count, true);

   bool keep = false;
   switch (mode) {
   case 0:
      /* Pure Turnip runtime feedback: no static keep bypass. */
      keep = false;
      break;
   case 1:
      /* Exact V45 heavy-pass policy: current best benchmark baseline. */
      keep = v45_keep;
      break;
   case 2:
      /* Isolate whether low-bandwidth members of V45's heavy set hurt. */
      keep = v45_keep && avg_bw >= 16;
      break;
   case 3:
      /* Require all three dimensions to agree; no additive compensation. */
      keep = (draws >= 20 && tile_count >= 8 && avg_bw >= 16) ||
             (draws >= 16 && tile_count >= 16 && avg_bw >= 16);
      break;
   case 4:
      /* Exact V46 pressure policy for regression/reference. */
      keep = frane_26346_keep_cb_pressure(cmd, tile_count, true);
      break;
   case 5:
      /* Upper-envelope probe: bypass feedback only for extreme work. */
      keep = draws >= 24 && tile_count >= 16 && avg_bw >= 24;
      break;
   default:
      /* Unknown modes fail back to the proven V45 baseline. */
      keep = v45_keep;
      break;
   }

   static const bool log_profile =
      debug_get_bool_option("TU_FRANE_CB_LOG", false);

   if (unlikely(log_profile)) {
      const unsigned admission_min =
         frane_26345_cb_min_draws(cmd, tile_count, true);
      const bool v46_keep =
         frane_26346_keep_cb_pressure(cmd, tile_count, true);

      mesa_logi("A810-CB47 mode=%u draws=%u tiles=%u bw=%u admit_min=%u "
                "score=%" PRIu64 " v45=%u v46=%u keep=%u",
                mode, draws, tile_count, avg_bw, admission_min,
                frane_26346_cb_pressure_score(cmd, tile_count),
                v45_keep, v46_keep, keep);
   }

   return keep;
}
'''

replacement = r'''static inline bool
frane_26347_keep_cb_profile_policy(const struct tu_cmd_buffer *cmd,
                                   uint32_t tile_count,
                                   bool gmem_path)
{
   if (!gmem_path || !frane_26344_a810_cb_override(cmd))
      return false;

   /* Smart CB1 uses a two-threshold policy:
    *
    *  - admission: moderate structural evidence, then normal Turnip GPU-side
    *    BV/BR feedback is allowed to disable CB if BR catches BV;
    *  - keep: only a narrow upper envelope bypasses that performance-only
    *    auto-disable check.
    *
    * This is deliberate hysteresis without a CPU/GPU readback loop: ordinary
    * passes can try CB without becoming sticky, while only clearly expensive
    * GMEM passes stay armed.
    */
   static const unsigned mode =
      debug_get_num_option("TU_FRANE_SMART_CB_MODE", 1);

   const uint32_t draws = cmd->state.rp.drawcall_count;
   const uint32_t avg_bw = frane_26345_avg_draw_bw(cmd);
   const bool v45_keep = frane_26345_keep_cb_heavy(cmd, tile_count, true);

   bool keep = false;
   switch (mode) {
   case 0:
      /* Pure runtime feedback. Safest A/B reference. */
      keep = false;
      break;
   case 1:
      /* Default: only strong multi-dimensional evidence may bypass Turnip's
       * BR-caught-BV feedback. One giant metric cannot compensate for weak
       * values in the others.
       */
      keep = (draws >= 28 && tile_count >= 12 && avg_bw >= 16) ||
             (draws >= 20 && tile_count >= 16 && avg_bw >= 24);
      break;
   case 2:
      /* Legacy V45 reference. */
      keep = v45_keep;
      break;
   case 3:
      /* Slightly more aggressive balanced gate. */
      keep = (draws >= 24 && tile_count >= 8 && avg_bw >= 16) ||
             (draws >= 18 && tile_count >= 16 && avg_bw >= 20);
      break;
   case 4:
      /* Legacy broad pressure policy for regression/reference only. */
      keep = frane_26346_keep_cb_pressure(cmd, tile_count, true);
      break;
   default:
      /* Unknown modes fail safe to runtime feedback only. */
      keep = false;
      break;
   }

   static const bool log_profile =
      debug_get_bool_option("TU_FRANE_SMART_CB_LOG", false);

   if (unlikely(log_profile)) {
      mesa_logi("A810-SMART-CB1 mode=%u draws=%u tiles=%u bw=%u "
                "admit_min=%u keep=%u",
                mode, draws, tile_count, avg_bw,
                frane_26345_cb_min_draws(cmd, tile_count, true), keep);
   }

   return keep;
}
'''

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    start,
    replacement,
    "replace V47 keep profiler with Smart-CB1 two-threshold policy",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    '"globally disabled / A810 adaptive policy"',
    '"globally disabled / A810 Smart CB1 policy"',
    "CB disable reason identity",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "A810 S1 Smart Performance 2 / Mesa ",
    "A810 S1 Smart CB1 / Mesa ",
    "Smart-CB1 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
dev = (V / "tu_device.cc").read_text()

for needle in (
    'TU_FRANE_SMART_CB", true',
    'TU_FRANE_SMART_CB_MODE", 1',
    'TU_FRANE_SMART_CB_LOG", false',
    "A810-SMART-CB1 mode=",
    "PIPE_BV_WAIT_FOR_BR",
    "PIPE_BR_WAIT_FOR_BV",
    "TU_ONCHIP_CB_RESLIST_OVERFLOW",
    "TU_PREDICATE_CB_ENABLED",
    "partial LRZ fast clear",
    "xfb/prim-gen/prim-counters/vtx-stats query is running",
):
    assert needle in cmd, needle

assert 'debug_get_bool_option("TU_A810_26344_SMART_CB", true)' not in cmd
assert 'debug_get_num_option("TU_FRANE_CB_MODE", 1)' not in cmd
assert "A810 S1 Smart CB1 / Mesa " in dev

print("A810 S1 Smart CB1 applied", flush=True)
