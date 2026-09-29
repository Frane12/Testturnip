#!/usr/bin/env python3
"""Drnas Turnip V46 CB-PRESSURE.

Layered on V45.

V45 made concurrent binning scene-aware and proved stable in the Crysis
three-pass benchmark. V46 keeps the V45 policy intact, but adds one narrow
experiment aimed at deterministic heavy-frame dips: a composite renderpass
pressure score can keep CB armed for expensive GMEM passes that are obviously
substantial but miss one of V45's rigid heavy-pass threshold combinations.

The score uses metrics Turnip/V45 already has:
  * draw count
  * GMEM tile count
  * average per-draw attachment bandwidth estimate

This does NOT change CB admission, correctness gates, synchronization, LRZ,
queries, resource overflow handling, or the V45 medium-pass GPU feedback path.

A/B:
  TU_A810_26346_CB_PRESSURE_SCORE=0
restores exact V45 heavy-pass keep behavior.

Tuning:
  TU_A810_26346_CB_PRESSURE_MIN=120
  TU_A810_26346_CB_PRESSURE_MIN_DRAWS=12
  TU_A810_26346_CB_PRESSURE_MIN_TILES=4
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
            f"V46 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V46 PASS {label}", flush=True)


anchor = r'''static inline bool
frane_26345_keep_cb_heavy(const struct tu_cmd_buffer *cmd,
                          uint32_t tile_count,
                          bool gmem_path)
{
   static const bool adaptive =
      debug_get_bool_option("TU_A810_26345_ADAPTIVE_CB", true);
   static const bool keep_heavy =
      debug_get_bool_option("TU_A810_26345_CB_KEEP_HEAVY", true);
   static const unsigned keep_draws =
      MAX2(1, debug_get_num_option("TU_A810_26345_CB_KEEP_DRAWS", 24));
   static const unsigned keep_tiles =
      MAX2(1, debug_get_num_option("TU_A810_26345_CB_KEEP_TILES", 8));

   if (!adaptive || !keep_heavy || !gmem_path ||
       !frane_26344_a810_cb_override(cmd))
      return false;

   const uint32_t draws = cmd->state.rp.drawcall_count;
   const uint32_t avg_bw = frane_26345_avg_draw_bw(cmd);

   /* The first arm is deliberately simple and robust.  The second admits a
    * smaller draw count only for a clearly wide/heavy tiled pass.
    */
   return (draws >= keep_draws && tile_count >= keep_tiles) ||
          (draws >= MAX2(12u, keep_draws / 2) &&
           tile_count >= MAX2(16u, keep_tiles * 2) &&
           avg_bw >= 16);
}
'''

replacement = r'''static inline bool
frane_26345_keep_cb_heavy(const struct tu_cmd_buffer *cmd,
                          uint32_t tile_count,
                          bool gmem_path)
{
   static const bool adaptive =
      debug_get_bool_option("TU_A810_26345_ADAPTIVE_CB", true);
   static const bool keep_heavy =
      debug_get_bool_option("TU_A810_26345_CB_KEEP_HEAVY", true);
   static const unsigned keep_draws =
      MAX2(1, debug_get_num_option("TU_A810_26345_CB_KEEP_DRAWS", 24));
   static const unsigned keep_tiles =
      MAX2(1, debug_get_num_option("TU_A810_26345_CB_KEEP_TILES", 8));

   if (!adaptive || !keep_heavy || !gmem_path ||
       !frane_26344_a810_cb_override(cmd))
      return false;

   const uint32_t draws = cmd->state.rp.drawcall_count;
   const uint32_t avg_bw = frane_26345_avg_draw_bw(cmd);

   /* The first arm is deliberately simple and robust.  The second admits a
    * smaller draw count only for a clearly wide/heavy tiled pass.
    */
   return (draws >= keep_draws && tile_count >= keep_tiles) ||
          (draws >= MAX2(12u, keep_draws / 2) &&
           tile_count >= MAX2(16u, keep_tiles * 2) &&
           avg_bw >= 16);
}

/* V46: preserve every V45 heavy-pass decision, then cover the "near miss"
 * region with a bounded composite pressure score.  This is intentionally only
 * used for the performance-only CB keep decision; it cannot admit a pass that
 * failed the normal V45 CB start policy.
 */
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

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    anchor,
    replacement,
    "add bounded CB pressure score",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (!TU_DEBUG(FORCE_CONCURRENT_BINNING) &&
       !frane_26345_keep_cb_heavy(cmd, tile_count, true)) {
""",
    """   if (!TU_DEBUG(FORCE_CONCURRENT_BINNING) &&
       !frane_26346_keep_cb_pressure(cmd, tile_count, true)) {
""",
    "use pressure-aware heavy-pass keep policy",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V45 / Mesa ",
    "Drnas Turnip V46 / Mesa ",
    "V46 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
dev = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()

for needle in (
    "TU_A810_26346_CB_PRESSURE_SCORE",
    "TU_A810_26346_CB_PRESSURE_MIN",
    "TU_A810_26346_CB_PRESSURE_MIN_DRAWS",
    "TU_A810_26346_CB_PRESSURE_MIN_TILES",
    "frane_26346_keep_cb_pressure",
):
    assert needle in cmd, needle

# Exact V45 policy remains available underneath the new scoring extension.
for needle in (
    "TU_A810_26345_ADAPTIVE_CB",
    "frane_26345_cb_policy_allows",
    "frane_26345_keep_cb_heavy",
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
assert "Drnas Turnip V46 / Mesa " in dev

print("Drnas Turnip V46 CB-PRESSURE applied", flush=True)
