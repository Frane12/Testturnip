#!/usr/bin/env python3
"""Drnas Turnip V47 CB-FLOW.

Layered on the proven V44 fixed-CB branch.

V44 showed a repeatable A810 gain when Turnip concurrent binning (CB) was
allowed. V45/V46 experiments that overrode CB's runtime keep/disable policy
were noisier or slower, so V47 deliberately keeps V44's known-good CB policy
and Turnip's own BV/BR runtime feedback intact.

The new experiment targets a different bottleneck: Turnip's HW-binning
admission heuristic.  That heuristic was designed around the cost of a normal
binning pass.  On A810, when concurrent binning is available, part of that
cost can overlap BR rendering, so a pass that is "not useful" for sequential
HW binning can still be worthwhile for CB.

V47 therefore promotes only a narrow class of borderline GMEM passes:
  * A810 custom CB path enabled;
  * VSC says HW binning is possible;
  * VSC's ordinary "binning_useful" result is false;
  * renderpass has at least N draws (default 8);
  * renderpass spans at least N GMEM tiles (default 2).

Everything else is exact V44 behavior.  Critically, V47 does NOT force CB to
stay on: the existing Turnip BV/BR timestamp feedback may still disable CB at
runtime when BR catches BV.

A/B:
  TU_A810_26347_FLOW_HW_BINNING=0
restores exact V44 HW-binning admission.

Tuning:
  TU_A810_26347_FLOW_MIN_DRAWS=8
  TU_A810_26347_FLOW_MIN_TILES=2
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


anchor = r'''static bool
use_hw_binning(struct tu_cmd_buffer *cmd)
{
   struct tu_framebuffer *fb = cmd->state.framebuffer;
   const struct tu_tiling_config *tiling =
      tu_framebuffer_get_tiling_config(fb, cmd->device, cmd->state.pass, cmd->state.gmem_layout, cmd->state.gmem_layout_divisor);
   const struct tu_vsc_config *vsc = tu_vsc_config(cmd, tiling);
'''

replacement = r'''static inline bool
frane_26347_promote_hw_binning(struct tu_cmd_buffer *cmd,
                               const struct tu_vsc_config *vsc)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26347_FLOW_HW_BINNING", true);

   if (!enabled || !frane_26344_a810_cb_override(cmd) ||
       !vsc->binning_possible || vsc->binning_useful)
      return false;

   static const unsigned min_draws =
      MAX2(1, debug_get_num_option("TU_A810_26347_FLOW_MIN_DRAWS", 8));
   static const unsigned min_tiles =
      MAX2(1, debug_get_num_option("TU_A810_26347_FLOW_MIN_TILES", 2));

   const uint32_t draws = cmd->state.rp.drawcall_count;
   const uint32_t tiles =
      vsc->tile_count.width * vsc->tile_count.height;

   /* This is intentionally a monotonic extension of V44:
    * - every pass V44 considered useful is unchanged;
    * - only a borderline "possible but not useful" pass may be promoted;
    * - CB's existing runtime feedback remains free to turn itself off.
    *
    * The draw/tile floor prevents tiny renderpasses from paying HW-binning
    * setup overhead just because CB exists.
    */
   return draws >= min_draws && tiles >= min_tiles;
}

static bool
use_hw_binning(struct tu_cmd_buffer *cmd)
{
   struct tu_framebuffer *fb = cmd->state.framebuffer;
   const struct tu_tiling_config *tiling =
      tu_framebuffer_get_tiling_config(fb, cmd->device, cmd->state.pass, cmd->state.gmem_layout, cmd->state.gmem_layout_divisor);
   const struct tu_vsc_config *vsc = tu_vsc_config(cmd, tiling);
'''

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    anchor,
    replacement,
    "add A810 CB-aware HW-binning promotion",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   return vsc->binning_possible && vsc->binning_useful;
}
""",
    """   if (vsc->binning_possible && vsc->binning_useful)
      return true;

   return frane_26347_promote_hw_binning(cmd, vsc);
}
""",
    "promote borderline HW-binning passes for concurrent flow",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip V44 / Mesa ",
    "Drnas Turnip V47 / Mesa ",
    "V47 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
dev = (V / "tu_device.cc").read_text()
autotune = (V / "tu_autotune.cc").read_text()
passcc = (V / "tu_pass.cc").read_text()

for needle in (
    "TU_A810_26347_FLOW_HW_BINNING",
    "TU_A810_26347_FLOW_MIN_DRAWS",
    "TU_A810_26347_FLOW_MIN_TILES",
    "frane_26347_promote_hw_binning",
):
    assert needle in cmd, needle

# Exact V44 CB machinery and A/B gate remain underneath.
for needle in (
    "TU_A810_26344_SMART_CB",
    "TU_A810_26344_CB_MIN_DRAWS",
    "frane_26344_a810_cb_override",
    "frane_26344_cb_policy_allows",
):
    assert needle in cmd, needle

# Keep Turnip's dynamic runtime feedback and every correctness guard intact.
for needle in (
    "TU_ONCHIP_CB_RESLIST_OVERFLOW",
    "PIPE_BV_WAIT_FOR_BR",
    "PIPE_BR_WAIT_FOR_BV",
    "TU_PREDICATE_CB_ENABLED",
    "BR_TIMESTAMP == BV_TIMESTAMP",
    "partial LRZ fast clear",
    "xfb/prim-gen/prim-counters/vtx-stats query is running",
):
    assert needle in cmd, needle

# Preserve the known-good rendering stack.
assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in passcc
assert "frane_gmem_search_future_upper" in passcc
assert 'TU_A810_26320_GMEM_TURBO", false' in autotune
assert "frane_26342_initiator_dynamic_dirty" in cmd
assert "frane_26342_bandwidth_dynamic_dirty" in cmd
assert "Drnas Turnip V47 / Mesa " in dev

print("Drnas Turnip V47 CB-FLOW applied", flush=True)
