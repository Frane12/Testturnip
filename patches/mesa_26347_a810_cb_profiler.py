#!/usr/bin/env python3
"""Drnas Turnip V47 CB-PROFILER.

Layered on V46/V45.

The previous Crysis A/B showed that the broad V46 composite pressure extension
was slower than exact V45 keep behavior, while the V45-style baseline itself
was extremely repeatable. V47 therefore stops guessing one new threshold and
turns the CB keep decision into an explicit profiler matrix.

The renderpass admission policy remains V45. V47 only selects which
performance-only "keep CB armed" bypass is allowed after a pass has already
entered CB. Turnip's correctness barriers, LRZ/query/resource guards and
BV/BR synchronization are untouched.

Modes (TU_A810_26347_CB_PROFILE_MODE):
  0 = runtime-only: never bypass Turnip BR/BV feedback
  1 = exact V45 heavy keep (default; current best baseline)
  2 = V45 heavy keep, but only when avg bandwidth >= 16
  3 = balanced 3-way gate:
        draws>=20, tiles>=8,  bw>=16
        OR
        draws>=16, tiles>=16, bw>=16
  4 = exact V46 pressure policy (regression/reference)
  5 = ultra-heavy only: draws>=24, tiles>=16, bw>=24

Optional structural telemetry:
  TU_A810_26347_CB_PROFILE_LOG=1

Logging is intentionally OFF by default because it perturbs CPU timing.
When enabled it prints one compact line per admitted GMEM CB renderpass:
  draws, tiles, avg bandwidth, adaptive admission threshold,
  V45/V46 decisions and selected keep decision.
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
            f"V47 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V47 PASS {label}", flush=True)


anchor = r'''static inline bool
frane_26346_keep_cb_pressure(const struct tu_cmd_buffer *cmd,
                             uint32_t tile_count,
                             bool gmem_path)
{
   if (frane_26345_keep_cb_heavy(cmd, tile_count, gmem_path))
      return true;

   static const bool enabled =
      debug_get_bool_option("TU_A810_26346_CB_PRESSURE_SCORE", true);

   if (!enabled || !gmem_path || !frane_26344_a810_cb_override(cmd))
      return false;

   static const unsigned min_score =
      MAX2(1, debug_get_num_option("TU_A810_26346_CB_PRESSURE_MIN", 120));
   static const unsigned min_draws =
      MAX2(1, debug_get_num_option("TU_A810_26346_CB_PRESSURE_MIN_DRAWS", 12));
   static const unsigned min_tiles =
      MAX2(1, debug_get_num_option("TU_A810_26346_CB_PRESSURE_MIN_TILES", 4));

   const uint32_t draws = cmd->state.rp.drawcall_count;
   if (draws < min_draws || tile_count < min_tiles)
      return false;

   const uint32_t avg_bw = frane_26345_avg_draw_bw(cmd);

   /* Cap the auxiliary terms so one extreme metric cannot dominate forever.
    * Weight draw count highest, then bandwidth, then tiled BR opportunity.
    */
   const uint64_t score =
      (uint64_t) draws * 4u +
      (uint64_t) MIN2(tile_count, 32u) * 3u +
      (uint64_t) MIN2(avg_bw, 64u) * 2u;

   return score >= min_score;
}
'''

replacement = r'''static inline uint64_t
frane_26346_cb_pressure_score(const struct tu_cmd_buffer *cmd,
                              uint32_t tile_count)
{
   const uint32_t draws = cmd->state.rp.drawcall_count;
   const uint32_t avg_bw = frane_26345_avg_draw_bw(cmd);

   return (uint64_t) draws * 4u +
          (uint64_t) MIN2(tile_count, 32u) * 3u +
          (uint64_t) MIN2(avg_bw, 64u) * 2u;
}

static inline bool
frane_26346_keep_cb_pressure(const struct tu_cmd_buffer *cmd,
                             uint32_t tile_count,
                             bool gmem_path)
{
   if (frane_26345_keep_cb_heavy(cmd, tile_count, gmem_path))
      return true;

   static const bool enabled =
      debug_get_bool_option("TU_A810_26346_CB_PRESSURE_SCORE", true);

   if (!enabled || !gmem_path || !frane_26344_a810_cb_override(cmd))
      return false;

   static const unsigned min_score =
      MAX2(1, debug_get_num_option("TU_A810_26346_CB_PRESSURE_MIN", 120));
   static const unsigned min_draws =
      MAX2(1, debug_get_num_option("TU_A810_26346_CB_PRESSURE_MIN_DRAWS", 12));
   static const unsigned min_tiles =
      MAX2(1, debug_get_num_option("TU_A810_26346_CB_PRESSURE_MIN_TILES", 4));

   const uint32_t draws = cmd->state.rp.drawcall_count;
   if (draws < min_draws || tile_count < min_tiles)
      return false;

   return frane_26346_cb_pressure_score(cmd, tile_count) >= min_score;
}

/* V47: controlled policy profiler.  The CPU-side admission decision is still
 * V45.  This only decides whether to bypass Turnip's performance-only
 * BR-caught-BV auto-disable check after CB has already been admitted.
 */
static inline bool
frane_26347_keep_cb_profile_policy(const struct tu_cmd_buffer *cmd,
                                   uint32_t tile_count,
                                   bool gmem_path)
{
   if (!gmem_path || !frane_26344_a810_cb_override(cmd))
      return false;

   static const unsigned mode =
      debug_get_num_option("TU_A810_26347_CB_PROFILE_MODE", 1);

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
      debug_get_bool_option("TU_A810_26347_CB_PROFILE_LOG", false);

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

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    anchor,
    replacement,
    "add CB keep profiler modes and optional telemetry",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (!TU_DEBUG(FORCE_CONCURRENT_BINNING) &&
       !frane_26346_keep_cb_pressure(cmd, tile_count, true)) {
""",
    """   if (!TU_DEBUG(FORCE_CONCURRENT_BINNING) &&
       !frane_26347_keep_cb_profile_policy(cmd, tile_count, true)) {
""",
    "route performance-only CB keep decision through V47 profiler",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V46 / Mesa ",
    "Drnas Turnip V47 / Mesa ",
    "V47 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
dev = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()

for needle in (
    "TU_A810_26347_CB_PROFILE_MODE",
    "TU_A810_26347_CB_PROFILE_LOG",
    "frane_26347_keep_cb_profile_policy",
    "frane_26346_cb_pressure_score",
    "A810-CB47 mode=",
):
    assert needle in cmd, needle

# V45 and V46 policies stay callable for exact A/B modes.
for needle in (
    "frane_26345_cb_policy_allows",
    "frane_26345_keep_cb_heavy",
    "frane_26346_keep_cb_pressure",
):
    assert needle in cmd, needle

# Keep Turnip correctness machinery intact.
for needle in (
    "TU_ONCHIP_CB_RESLIST_OVERFLOW",
    "PIPE_BV_WAIT_FOR_BR",
    "PIPE_BR_WAIT_FOR_BV",
    "TU_PREDICATE_CB_ENABLED",
    "partial LRZ fast clear",
    "xfb/prim-gen/prim-counters/vtx-stats query is running",
):
    assert needle in cmd, needle

# Preserve proven rendering baseline.
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert "Drnas Turnip V47 / Mesa " in dev

print("Drnas Turnip V47 CB-PROFILER applied", flush=True)
