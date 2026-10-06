#!/usr/bin/env python3
"""S2.2 Q-LRZ clean-room renderpass policy.

Applied after S2's V38 SH1 + GF1 patches.  This patch does not copy proprietary
Qualcomm code and does not alter Vulkan correctness, LRZ enable/disable rules,
barriers, attachment allocation, tile geometry, or synchronization.

It adds:
  * renderpass draw/depth/stencil/LRZ behaviour counters;
  * explicit indirect-command accounting;
  * a separately-switchable A810 Q-policy input;
  * a bounded -12..+10 structural delta to SMART-GMEM.

TU_FRANE_S22_Q_POLICY=0 restores S2 policy behaviour in the same binary.
"""
from pathlib import Path
import shutil

V = Path("mesa/src/freedreno/vulkan")


def edit(rel, old, new, label):
    p = V / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"S2.2 source drift {label}: expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"S2.2 PASS {label}", flush=True)


def replace_count(rel, old, new, expected, label):
    p = V / rel
    s = p.read_text()
    n = s.count(old)
    if n != expected:
        raise SystemExit(
            f"S2.2 source drift {label}: expected {expected}, saw {n}: {old!r}"
        )
    p.write_text(s.replace(old, new))
    print(f"S2.2 PASS {label}: {n}", flush=True)


# Pure policy helper is versioned in the downstream repo and copied into Mesa.
shutil.copyfile(
    "patches/frane_s22_q_policy.h",
    V / "frane_s22_q_policy.h",
)

# Extend the existing S2 SMART-GMEM input and blend only a bounded signed delta.
edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    '#include "frane_mesa_2634_a810_gmem_runtime.h"\n',
    '#include "frane_mesa_2634_a810_gmem_runtime.h"\n'
    '#include "frane_s22_q_policy.h"\n',
    "include Q policy helper",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   uint32_t peak_live_planes = 0;
};""",
    """   uint32_t peak_live_planes = 0;

   /* S2.2 clean-room renderpass behaviour metadata. Zero means unavailable. */
   uint32_t q_draw_count = 0;
   uint32_t q_indirect_draw_count = 0;
   uint32_t q_depth_test_draw_count = 0;
   uint32_t q_depth_write_draw_count = 0;
   uint32_t q_stencil_draw_count = 0;
   uint32_t q_stencil_write_draw_count = 0;
   uint32_t q_lrz_candidate_draw_count = 0;
   uint32_t q_lrz_late_draw_count = 0;
   uint32_t q_stencil_last_draw = 0;
   uint32_t q_lrz_disabled_at_draw_plus1 = 0;
   uint32_t q_lrz_write_disabled_at_draw_plus1 = 0;
};""",
    "extend SMART-GMEM input with renderpass behaviour",
)

edit(
    "frane_mesa_26318_a810_smart_gmem.h",
    """   const auto gf1 = frane_v38_gf1_eval_footprint(in);
   if (gf1.valid)
      score += gf1.score_bonus;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    """   const auto gf1 = frane_v38_gf1_eval_footprint(in);
   if (gf1.valid)
      score += gf1.score_bonus;

   frane_s22_q_rp_input q_in {};
   q_in.draw_count = in.q_draw_count;
   q_in.indirect_draw_count = in.q_indirect_draw_count;
   q_in.depth_test_draw_count = in.q_depth_test_draw_count;
   q_in.depth_write_draw_count = in.q_depth_write_draw_count;
   q_in.stencil_draw_count = in.q_stencil_draw_count;
   q_in.stencil_write_draw_count = in.q_stencil_write_draw_count;
   q_in.lrz_candidate_draw_count = in.q_lrz_candidate_draw_count;
   q_in.lrz_late_draw_count = in.q_lrz_late_draw_count;
   q_in.stencil_last_draw = in.q_stencil_last_draw;
   q_in.lrz_disabled_at_draw_plus1 = in.q_lrz_disabled_at_draw_plus1;
   q_in.lrz_write_disabled_at_draw_plus1 =
      in.q_lrz_write_disabled_at_draw_plus1;
   q_in.sysmem_bandwidth_per_pixel = in.sysmem_bandwidth_per_pixel;
   q_in.gmem_bandwidth_per_pixel = in.gmem_bandwidth_per_pixel;

   const auto q_eval = frane_s22_q_eval(q_in);
   if (q_eval.valid)
      score += q_eval.score_delta;

   out.structure_score = uint8_t(std::clamp(score, 0, 100));""",
    "blend bounded Q score into structural prior",
)

# Store per-renderpass metrics next to Turnip's existing autotune counters.
edit(
    "tu_cmd_buffer.h",
    """   uint32_t drawcall_count;

   /* A calculated "draw cost" value for renderpass""",
    """   uint32_t drawcall_count;

   /* S2.2 Q-LRZ: observation only; never used to bypass LRZ correctness. */
   uint32_t frane_s22_indirect_draw_count;
   uint32_t frane_s22_depth_test_draw_count;
   uint32_t frane_s22_depth_write_draw_count;
   uint32_t frane_s22_stencil_draw_count;
   uint32_t frane_s22_stencil_write_draw_count;
   uint32_t frane_s22_lrz_candidate_draw_count;
   uint32_t frane_s22_lrz_late_draw_count;
   uint32_t frane_s22_stencil_last_draw;

   /* A calculated "draw cost" value for renderpass""",
    "add renderpass observation counters",
)

# Make indirectness explicit instead of inferring it from a zero primitive count.
edit(
    "tu_cmd_buffer.cc",
    """tu6_draw_common(struct tu_cmd_buffer *cmd,
                struct tu_cs *cs,
                bool indexed,
                /* note: draw_count is 0 for indirect */
                uint32_t draw_count)""",
    """tu6_draw_common(struct tu_cmd_buffer *cmd,
                struct tu_cs *cs,
                bool indexed,
                bool indirect,
                uint32_t draw_count)""",
    "add explicit indirect draw argument",
)

for old, new, expected, label in (
    ("tu6_draw_common<CHIP>(cmd, cs, false, vertexCount);",
     "tu6_draw_common<CHIP>(cmd, cs, false, false, vertexCount);", 1,
     "direct draw call"),
    ("tu6_draw_common<CHIP>(cmd, cs, false, max_vertex_count);",
     "tu6_draw_common<CHIP>(cmd, cs, false, false, max_vertex_count);", 1,
     "multi direct draw call"),
    ("tu6_draw_common<CHIP>(cmd, cs, true, indexCount);",
     "tu6_draw_common<CHIP>(cmd, cs, true, false, indexCount);", 1,
     "indexed draw call"),
    ("tu6_draw_common<CHIP>(cmd, cs, true, max_index_count);",
     "tu6_draw_common<CHIP>(cmd, cs, true, false, max_index_count);", 1,
     "multi indexed draw call"),
    ("tu6_draw_common<CHIP>(cmd, cs, false, 0);",
     "tu6_draw_common<CHIP>(cmd, cs, false, true, 0);", 3,
     "non-indexed indirect draw calls"),
    ("tu6_draw_common<CHIP>(cmd, cs, true, 0);",
     "tu6_draw_common<CHIP>(cmd, cs, true, true, 0);", 2,
     "indexed indirect draw calls"),
):
    replace_count("tu_cmd_buffer.cc", old, new, expected, label)

edit(
    "tu_cmd_buffer.cc",
    """   /* Fill draw stats for autotuner */
   rp->drawcall_count++;

   rp->drawcall_bandwidth_per_sample_sum +=""",
    """   /* Fill draw stats for autotuner */
   rp->drawcall_count++;

   /*
    * S2.2 Q-LRZ observation.  Keep this after dynamic state emission so the
    * counters describe the state actually used by this draw.  These counters
    * never enable LRZ or alter depth/stencil state.
    */
   if (indirect)
      rp->frane_s22_indirect_draw_count++;

   const bool frane_depth_test =
      cmd->vk.dynamic_graphics_state.ds.depth.test_enable;
   const bool frane_depth_write =
      tu6_writes_depth(cmd, frane_depth_test);
   const bool frane_stencil_test =
      cmd->vk.dynamic_graphics_state.ds.stencil.test_enable;
   const bool frane_stencil_write = tu6_writes_stencil(cmd);

   if (frane_depth_test)
      rp->frane_s22_depth_test_draw_count++;
   if (frane_depth_write)
      rp->frane_s22_depth_write_draw_count++;
   if (frane_stencil_test) {
      rp->frane_s22_stencil_draw_count++;
      rp->frane_s22_stencil_last_draw = rp->drawcall_count;
   }
   if (frane_stencil_write)
      rp->frane_s22_stencil_write_draw_count++;

   if (frane_depth_test && cmd->state.lrz.enabled) {
      rp->frane_s22_lrz_candidate_draw_count++;

      const struct tu_shader *frane_fs =
         cmd->state.shaders[MESA_SHADER_FRAGMENT];
      if (frane_fs && frane_fs->variant) {
         const bool frane_user_early =
            frane_fs->variant->fs.early_fragment_tests;
         const bool frane_late_risk =
            !frane_user_early &&
            (frane_fs->variant->has_kill ||
             frane_fs->variant->writes_smask ||
             frane_fs->variant->writes_pos ||
             frane_fs->fs.sample_shading ||
             frane_fs->fs.lrz.force_late_z ||
             cmd->state.lrz.force_late_z ||
             cmd->vk.dynamic_graphics_state.ms.alpha_to_coverage_enable);
         if (frane_late_risk)
            rp->frane_s22_lrz_late_draw_count++;
      }
   }

   rp->drawcall_bandwidth_per_sample_sum +=""",
    "collect draw/depth/stencil/LRZ behaviour",
)

# Preserve the metrics across secondary-command-buffer / suspend-resume merges.
edit(
    "tu_cmd_buffer.cc",
    """   dst->drawcall_bandwidth_per_sample_sum +=
      src->drawcall_bandwidth_per_sample_sum;
   if (!dst->lrz_disable_reason && src->lrz_disable_reason) {""",
    """   dst->drawcall_bandwidth_per_sample_sum +=
      src->drawcall_bandwidth_per_sample_sum;

   dst->frane_s22_indirect_draw_count +=
      src->frane_s22_indirect_draw_count;
   dst->frane_s22_depth_test_draw_count +=
      src->frane_s22_depth_test_draw_count;
   dst->frane_s22_depth_write_draw_count +=
      src->frane_s22_depth_write_draw_count;
   dst->frane_s22_stencil_draw_count +=
      src->frane_s22_stencil_draw_count;
   dst->frane_s22_stencil_write_draw_count +=
      src->frane_s22_stencil_write_draw_count;
   dst->frane_s22_lrz_candidate_draw_count +=
      src->frane_s22_lrz_candidate_draw_count;
   dst->frane_s22_lrz_late_draw_count +=
      src->frane_s22_lrz_late_draw_count;
   if (src->frane_s22_stencil_last_draw) {
      dst->frane_s22_stencil_last_draw =
         MAX2(dst->frane_s22_stencil_last_draw,
              dst->drawcall_count + src->frane_s22_stencil_last_draw);
   }

   if (!dst->lrz_disable_reason && src->lrz_disable_reason) {""",
    "merge renderpass observation counters",
)

# Independent A/B gate; disabling this leaves the existing S2 GF1 metadata live.
edit(
    "tu_autotune.cc",
    """static bool
frane_a810_gmem_footprint_enabled(const struct tu_device *device)
{""",
    """static bool
frane_a810_s22_q_policy_enabled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_S22_Q_POLICY", true);
   if (!enabled || !device || !device->physical_device)
      return false;

   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44010000) ||
          id == UINT64_C(0xffff44010000);
}

static bool
frane_a810_gmem_footprint_enabled(const struct tu_device *device)
{""",
    "add default-on A810 Q-policy gate",
)

edit(
    "tu_autotune.cc",
    """         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;""",
    """         if (frane_a810_s22_q_policy_enabled(device)) {
            const struct tu_render_pass_state &q_rp = cmd_state->rp;
            runtime_input.q_draw_count = q_rp.drawcall_count;
            runtime_input.q_indirect_draw_count =
               q_rp.frane_s22_indirect_draw_count;
            runtime_input.q_depth_test_draw_count =
               q_rp.frane_s22_depth_test_draw_count;
            runtime_input.q_depth_write_draw_count =
               q_rp.frane_s22_depth_write_draw_count;
            runtime_input.q_stencil_draw_count =
               q_rp.frane_s22_stencil_draw_count;
            runtime_input.q_stencil_write_draw_count =
               q_rp.frane_s22_stencil_write_draw_count;
            runtime_input.q_lrz_candidate_draw_count =
               q_rp.frane_s22_lrz_candidate_draw_count;
            runtime_input.q_lrz_late_draw_count =
               q_rp.frane_s22_lrz_late_draw_count;
            runtime_input.q_stencil_last_draw =
               q_rp.frane_s22_stencil_last_draw;

            if (q_rp.lrz_disable_reason) {
               runtime_input.q_lrz_disabled_at_draw_plus1 =
                  q_rp.lrz_disabled_at_draw == UINT32_MAX
                     ? UINT32_MAX
                     : q_rp.lrz_disabled_at_draw + 1;
            }
            if (q_rp.lrz_write_disable_reason) {
               runtime_input.q_lrz_write_disabled_at_draw_plus1 =
                  q_rp.lrz_write_disabled_at_draw == UINT32_MAX
                     ? UINT32_MAX
                     : q_rp.lrz_write_disabled_at_draw + 1;
            }
         }

         runtime_input.sysmem_bandwidth_per_pixel =
            pass->sysmem_bandwidth_per_pixel;
         runtime_input.gmem_bandwidth_per_pixel =
            pass->gmem_bandwidth_per_pixel;""",
    "feed renderpass observations into SMART-GMEM",
)

# Sanity checks: keep the scope explicit and make A/B recovery auditable.
h = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
c = (V / "tu_cmd_buffer.cc").read_text()
ch = (V / "tu_cmd_buffer.h").read_text()
a = (V / "tu_autotune.cc").read_text()

for needle in (
    "frane_s22_q_eval",
    "q_indirect_draw_count",
    "q_lrz_candidate_draw_count",
    "q_lrz_disabled_at_draw_plus1",
):
    assert needle in h, needle

for needle in (
    "frane_s22_indirect_draw_count",
    "frane_s22_lrz_candidate_draw_count",
    "frane_s22_lrz_late_draw_count",
    "bool indirect",
):
    assert needle in c, needle
    assert needle in ch or needle == "bool indirect", needle

for needle in (
    'TU_FRANE_S22_Q_POLICY", true',
    "runtime_input.q_draw_count",
    "runtime_input.q_lrz_write_disabled_at_draw_plus1",
):
    assert needle in a, needle

assert (V / "frane_s22_q_policy.h").read_text() == Path(
    "patches/frane_s22_q_policy.h"
).read_text()

print("S2.2 Q-LRZ clean-room renderpass policy applied", flush=True)
