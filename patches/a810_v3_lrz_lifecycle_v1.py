#!/usr/bin/env python3
"""A810 V3 LRZ lifecycle experiment.

Strict derivative of Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP.
The V3 code/branch is left untouched.

Goal:
  Avoid A8xx LRZ command-stream work in renderpasses that have no LRZ/depth
  image bound at all.  This does NOT change LRZ decisions for depth passes,
  GMEM/SYSMEM selection, shader code, or depth-test semantics.

Optimizations (A810 only, default ON):
  1. tu_lrz_after_bv(): do not emit FD_LRZ_FLUSH for a pass with no LRZ image.
  2. tu_lrz_before_tiles(): do not touch TU_PREDICATE_FIRST_TILE when there is
     no LRZ image.  The predicate exists only for the LRZ flip path.
  3. tu_lrz_tiling_end(): keep the normal LRZ disable programming, but skip the
     final LRZ cache flush when no LRZ resource participated in the pass.

A/B:
  TU_A810_V3_LRZ_LIFECYCLE=0 -> exact V3 LRZ lifecycle behavior.
  unset / 1                  -> optimized A810 no-depth behavior.

All depth/LRZ-active paths remain byte-for-byte on the legacy control flow.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"A810 V3 LRZ lifecycle source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"A810 V3 LRZ-LIFECYCLE PASS {label}", flush=True)


edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    '#include "tu_tracepoints.h"\n#include "tu_trace_bin_layout.h"\n',
    '#include "tu_tracepoints.h"\n#include "tu_trace_bin_layout.h"\n#include "util/u_debug.h"\n',
    "include debug option helper",
)

edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """template <chip CHIP>
void
tu_lrz_after_bv(struct tu_cmd_buffer *cmd, struct tu_cs *cs)
{
   if (CHIP < A7XX)
      return;

   /* BV and BR have different LRZ caches, so flush LRZ cache to be read by
    * BR.
    */
""",
    """static bool
frane_a810_v3_lrz_lifecycle(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_V3_LRZ_LIFECYCLE", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == 0x44010000ull || chip == 0xffff44010000ull;
}

template <chip CHIP>
void
tu_lrz_after_bv(struct tu_cmd_buffer *cmd, struct tu_cs *cs)
{
   if (CHIP < A7XX)
      return;

   /* No LRZ resource participated in this renderpass, so there is no BV LRZ
    * cache content that BR can consume.  Keep legacy behavior on every other
    * GPU and when the A/B switch is disabled.
    */
   if (frane_a810_v3_lrz_lifecycle(cmd) && !cmd->state.lrz.image_view)
      return;

   /* BV and BR have different LRZ caches, so flush LRZ cache to be read by
    * BR.
    */
""",
    "skip no-resource BV LRZ flush on A810",
)

edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """template <chip CHIP>
void
tu_lrz_before_tiles(struct tu_cmd_buffer *cmd, struct tu_cs *cs, bool use_cb)
{
   if (CHIP < A7XX)
      return;

   tu7_set_pred_bit(cs, TU_PREDICATE_FIRST_TILE, true);

   if (!cmd->state.lrz.image_view)
      return;
""",
    """template <chip CHIP>
void
tu_lrz_before_tiles(struct tu_cmd_buffer *cmd, struct tu_cs *cs, bool use_cb)
{
   if (CHIP < A7XX)
      return;

   const bool frane_lifecycle = frane_a810_v3_lrz_lifecycle(cmd);

   /* FIRST_TILE is consumed only by the LRZ flip path below.  On A810,
    * avoid programming it for color-only/no-depth passes.  A/B-off preserves
    * the original ordering exactly.
    */
   if (!frane_lifecycle)
      tu7_set_pred_bit(cs, TU_PREDICATE_FIRST_TILE, true);

   if (!cmd->state.lrz.image_view)
      return;

   if (frane_lifecycle)
      tu7_set_pred_bit(cs, TU_PREDICATE_FIRST_TILE, true);
""",
    "avoid FIRST_TILE LRZ predicate write on no-depth A810 passes",
)

edit(
    "src/freedreno/vulkan/tu_lrz.cc",
    """   if (cmd->state.lrz.gpu_dir_tracking && disable_for_next_rp) {
      tu6_write_lrz_reg(cmd, cs, A6XX_GRAS_LRZ_VIEW_INFO(
         .base_layer = 0b11111111111,
         .layer_count = 0b11111111111,
         .base_mip_level = 0b1111,
      ));

      tu_emit_event_write<CHIP>(cmd, cs, FD_LRZ_CLEAR);
      tu_emit_event_write<CHIP>(cmd, cs, FD_LRZ_FLUSH);
   } else {
      tu_emit_event_write<CHIP>(cmd, cs, FD_LRZ_FLUSH);
   }
}
TU_GENX(tu_lrz_tiling_end);
""",
    """   if (cmd->state.lrz.gpu_dir_tracking && disable_for_next_rp) {
      tu6_write_lrz_reg(cmd, cs, A6XX_GRAS_LRZ_VIEW_INFO(
         .base_layer = 0b11111111111,
         .layer_count = 0b11111111111,
         .base_mip_level = 0b1111,
      ));

      tu_emit_event_write<CHIP>(cmd, cs, FD_LRZ_CLEAR);
      tu_emit_event_write<CHIP>(cmd, cs, FD_LRZ_FLUSH);
   } else if (!(frane_a810_v3_lrz_lifecycle(cmd) &&
                !cmd->state.lrz.image_view)) {
      /* Color-only A810 renderpasses never touched an LRZ resource.  The
       * disable programming above is retained, but an LRZ cache flush has no
       * producer/consumer to synchronize in this pass.
       */
      tu_emit_event_write<CHIP>(cmd, cs, FD_LRZ_FLUSH);
   }
}
TU_GENX(tu_lrz_tiling_end);
""",
    "skip final no-resource LRZ flush while retaining disable programming",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP / Mesa ",
    "Frane A810 V3 LRZ-LIFECYCLE V1 / Mesa ",
    "experimental driver identity",
)

lrz = (ROOT / "src/freedreno/vulkan/tu_lrz.cc").read_text()
dev = (ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

assert 'TU_A810_V3_LRZ_LIFECYCLE' in lrz
assert 'frane_a810_v3_lrz_lifecycle' in lrz
assert '&& !cmd->state.lrz.image_view' in lrz
assert 'if (!frane_lifecycle)' in lrz
assert 'if (frane_lifecycle)' in lrz
assert 'FD_LRZ_FLUSH' in lrz
assert 'Frane A810 V3 LRZ-LIFECYCLE V1' in dev

# The V3 LRZ fastpath must still be present and unchanged by this patch.
cmd = (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
pipe = (ROOT / "src/freedreno/vulkan/tu_pipeline.cc").read_text()
assert 'TU_A810_26313_LRZ_FASTPATH' in cmd
assert 'frane_26313_same_lrz_fs_signature' in cmd
assert 'TU_A810_26313_LRZ_FASTPATH' in pipe

print("A810 V3 LRZ-LIFECYCLE V1 applied", flush=True)
