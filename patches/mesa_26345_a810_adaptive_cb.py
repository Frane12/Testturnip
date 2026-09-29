#!/usr/bin/env python3
"""Drnas Turnip V45 ADAPTIVE-CB.

Layered on V44/V42/V39.

V44 proved that A810 can gain real throughput from Turnip concurrent binning.
V45 makes the policy scene-aware instead of using one fixed draw-count gate.

The policy has two layers:

1. CPU-side admission:
   * current render-pass draw count;
   * GMEM tile count;
   * average per-draw bandwidth estimate already tracked by Turnip.
   This derives an adaptive minimum draw count.

2. GPU-side runtime policy:
   * Turnip's normal BV/BR timestamp test remains active for medium passes;
   * only very heavy GMEM passes may keep CB armed instead of letting the
     performance-only "BR caught BV" heuristic disable it.

All correctness gates remain untouched: LRZ restrictions, partial fast-clear
protection, queries, resource overflow, CB barrier patchpoints and BV/BR
synchronization are preserved.

A/B:
  TU_A810_26345_ADAPTIVE_CB=0
restores the V44 fixed-threshold policy.

Tuning:
  TU_A810_26345_CB_BASE_DRAWS=8
  TU_A810_26345_CB_KEEP_HEAVY=1
  TU_A810_26345_CB_KEEP_DRAWS=24
  TU_A810_26345_CB_KEEP_TILES=8
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
            f"V45 source drift at {label}: expected 1 anchor, found {n}: "
            f"{old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"V45 PASS {label}", flush=True)


anchor = r'''static inline bool
frane_26344_cb_policy_allows(const struct tu_cmd_buffer *cmd)
{
   /* Preserve Mesa's explicit/DRI enable exactly, including force-CB. */
   if (cmd->device->instance->drirc.perf.allow_concurrent_binning)
      return true;

   if (!frane_26344_a810_cb_override(cmd))
      return false;

   static const unsigned min_draws =
      MAX2(1, debug_get_num_option("TU_A810_26344_CB_MIN_DRAWS", 8));

   return cmd->state.rp.drawcall_count >= min_draws;
}
'''

replacement = r'''static inline bool
frane_26344_cb_policy_allows(const struct tu_cmd_buffer *cmd)
{
   /* Preserve Mesa's explicit/DRI enable exactly, including force-CB. */
   if (cmd->device->instance->drirc.perf.allow_concurrent_binning)
      return true;

   if (!frane_26344_a810_cb_override(cmd))
      return false;

   static const unsigned min_draws =
      MAX2(1, debug_get_num_option("TU_A810_26344_CB_MIN_DRAWS", 8));

   return cmd->state.rp.drawcall_count >= min_draws;
}

/* V45: scene-aware CB admission.  This intentionally consumes metrics Turnip
 * already computes for every renderpass, so the policy itself has essentially
 * no new per-draw bookkeeping cost.
 */
static inline uint32_t
frane_26345_avg_draw_bw(const struct tu_cmd_buffer *cmd)
{
   const uint32_t draws = cmd->state.rp.drawcall_count;
   if (!draws)
      return 0;

   return cmd->state.rp.drawcall_bandwidth_per_sample_sum / draws;
}

static inline unsigned
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

static inline bool
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

static inline bool
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

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    anchor,
    replacement,
    "add adaptive CB admission and heavy-pass keep policy",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """static bool
tu7_emit_concurrent_binning_start(struct tu_cmd_buffer *cmd,
                                  struct tu_cs *cs,
                                  bool disable_cb)
""",
    """static bool
tu7_emit_concurrent_binning_start(struct tu_cmd_buffer *cmd,
                                  struct tu_cs *cs,
                                  bool disable_cb,
                                  uint32_t tile_count,
                                  bool gmem_path)
""",
    "extend CB start with renderpass context",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """       tu7_cb_disable_reason(!frane_26344_cb_policy_allows(cmd), cmd,
                             "globally disabled / A810 pass too small")) {
""",
    """       tu7_cb_disable_reason(!frane_26345_cb_policy_allows(cmd, tile_count, gmem_path), cmd,
                             "globally disabled / A810 adaptive policy")) {
""",
    "use V45 adaptive CB admission",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """      if (tu7_emit_concurrent_binning_start(cmd, cs, false)) {
""",
    """      if (tu7_emit_concurrent_binning_start(cmd, cs, false, 0, false)) {
""",
    "tag sysmem CB path",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """static bool
tu7_emit_concurrent_binning_gmem(struct tu_cmd_buffer *cmd, struct tu_cs *cs,
                                 bool use_hw_binning)
""",
    """static bool
tu7_emit_concurrent_binning_gmem(struct tu_cmd_buffer *cmd, struct tu_cs *cs,
                                 bool use_hw_binning,
                                 uint32_t tile_count)
""",
    "pass GMEM tile count into CB path",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (!tu7_emit_concurrent_binning_start(cmd, cs, disable_cb || !use_hw_binning))
""",
    """   if (!tu7_emit_concurrent_binning_start(cmd, cs,
                                                disable_cb || !use_hw_binning,
                                                tile_count, true))
""",
    "tag GMEM CB path",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (!TU_DEBUG(FORCE_CONCURRENT_BINNING)) {
""",
    """   if (!TU_DEBUG(FORCE_CONCURRENT_BINNING) &&
       !frane_26345_keep_cb_heavy(cmd, tile_count, true)) {
""",
    "keep CB armed on structurally heavy A810 GMEM passes",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """      use_cb = tu7_emit_concurrent_binning_gmem(cmd, cs, use_binning);
""",
    """      use_cb = tu7_emit_concurrent_binning_gmem(cmd, cs, use_binning,
                                                    tile_count);
""",
    "feed tile count to GMEM CB policy",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V44 / Mesa ",
    "Drnas Turnip V45 / Mesa ",
    "V45 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
dev = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()

for needle in (
    "TU_A810_26345_ADAPTIVE_CB",
    "TU_A810_26345_CB_BASE_DRAWS",
    "TU_A810_26345_CB_KEEP_HEAVY",
    "frane_26345_avg_draw_bw",
    "frane_26345_cb_min_draws",
    "frane_26345_cb_policy_allows",
    "frane_26345_keep_cb_heavy",
):
    assert needle in cmd, needle

# V44 A/B and A810 gate remain available.
assert "TU_A810_26344_SMART_CB" in cmd
assert "frane_26344_a810_cb_override" in cmd

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
assert "Drnas Turnip V45 / Mesa " in dev

print("Drnas Turnip V45 ADAPTIVE-CB applied", flush=True)
