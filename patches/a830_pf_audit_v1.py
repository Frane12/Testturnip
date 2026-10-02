#!/usr/bin/env python3
"""Drnas Turnip A830 PF-AUDIT V1.0.

Base: Drnas Turnip A830 V59 LRZ-CLEAN.

Purpose:
  Isolate A830/8 Elite GMEM write-page-fault classes while running ordinary
  games/benchmarks.  The user only changes one short environment variable:

      TU_FRANE_PF=0..8

No logcat, kernel trace or internal command-stream scraping is required for the
first bisection.  Crash/stability + benchmark behavior is the signal.

Modes:
  0 NORMAL      Current A830 V59 + V2 adaptive-GMEM baseline.
  1 SYSMEM      Force SYSMEM for every otherwise-valid A830 render pass.
  2 GMEM        Force GMEM whenever Mesa's mandatory correctness gates allow it.
  3 NO-RESOLVE  Quarantine passes that perform fixed/custom/MSRTSS resolves.
  4 NO-MSAA     Quarantine multisampled/MSRTSS passes.
  5 NO-DS       Quarantine depth/stencil GMEM passes.
  6 NO-STORE    Quarantine passes that store a GMEM attachment to memory.
  7 SAFE-COLOR  GMEM is allowed only for single-sample, color-only,
                non-resolve passes; all other classes go to SYSMEM.
  8 V2-OFF      Keep normal Mesa selection but disable only the A830 V2
                measured boost/tail learner, testing transition/override logic.

"Quarantine" means the selected class is forced to SYSMEM. Other passes retain
normal selection. Mandatory Mesa safety gates (impossible GMEM layout, empty
render area, tessellation restrictions, XFB/query restrictions, etc.) always
win over mode 2.

This diagnostic layer does not alter GMEM offsets, CCU/VPC programming,
barriers, resolves, image layouts, UBWC, LRZ rules or synchronization.
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
            f"A830 PF-AUDIT V1.0 source drift at {label}: "
            f"expected 1 anchor, found {n}: {old[:260]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"A830 PF-AUDIT V1.0 PASS {label}", flush=True)


edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    '#include "vk_util.h"\n',
    '#include "vk_util.h"\n#include "util/u_debug.h"\n',
    "explicit u_debug include",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """static bool
use_sysmem_rendering(struct tu_cmd_buffer *cmd,
                     tu_autotune::rp_ctx_t *rp_ctx,
                     tu_autotune::rp_key_opt rp_key)
{""",
    """struct frane_a830_pf_risk {
   bool msaa;
   bool depth_stencil;
   bool resolve;
   bool store;
   bool load;
};

static bool
frane_a830_pf_gpu(const struct tu_cmd_buffer *cmd)
{
   if (!cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t id = cmd->device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44050000) ||
          id == UINT64_C(0x44050001) ||
          id == UINT64_C(0xffff44050000);
}

static uint8_t
frane_a830_pf_mode(void)
{
   /* Process-static by design: Winlator shortcut variables do not change
    * while the process is alive, so do not reparse getenv on every RP.
    */
   static const int64_t raw =
      debug_get_num_option("TU_FRANE_PF", 0);

   if (raw <= 0)
      return 0;
   if (raw >= 8)
      return 8;
   return (uint8_t) raw;
}

static struct frane_a830_pf_risk
frane_a830_pf_classify(const struct tu_render_pass *pass)
{
   struct frane_a830_pf_risk out = {};

   if (!pass)
      return out;

   out.msaa = pass->has_msrtss;
   out.resolve = pass->has_msrtss;

   for (uint32_t i = 0; i < pass->attachment_count; i++) {
      const struct tu_render_pass_attachment *att = &pass->attachments[i];

      /* Only classify work that can participate in the GMEM path. */
      if (!att->gmem)
         continue;

      if (att->samples != VK_SAMPLE_COUNT_1_BIT)
         out.msaa = true;

      if (vk_format_has_depth(att->format) ||
          vk_format_has_stencil(att->format))
         out.depth_stencil = true;

      if (att->will_be_resolved)
         out.resolve = true;

      if (att->store || att->store_stencil)
         out.store = true;

      if (att->load || att->load_stencil)
         out.load = true;
   }

   for (uint32_t i = 0; i < pass->subpass_count; i++) {
      const struct tu_subpass *subpass = &pass->subpasses[i];
      if (subpass->custom_resolve || subpass->resolve_depth_stencil)
         out.resolve = true;
   }

   return out;
}

static bool
use_sysmem_rendering(struct tu_cmd_buffer *cmd,
                     tu_autotune::rp_ctx_t *rp_ctx,
                     tu_autotune::rp_key_opt rp_key)
{""",
    "insert exact-A830 PF classifier",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (TU_DEBUG(SYSMEM)) {
      cmd->state.rp.force_render_mode_reason = "TU_DEBUG(SYSMEM)";
      return true;
   }

   /* can't fit attachments into gmem */""",
    """   if (TU_DEBUG(SYSMEM)) {
      cmd->state.rp.force_render_mode_reason = "TU_DEBUG(SYSMEM)";
      return true;
   }

   const uint8_t frane_pf_mode =
      frane_a830_pf_gpu(cmd) ? frane_a830_pf_mode() : 0;

   /* Mode 1 is the cleanest control: never enter the A830 GMEM path. */
   if (frane_pf_mode == 1) {
      cmd->state.rp.force_render_mode_reason =
         "TU_FRANE_PF=1: A830 PF audit forced SYSMEM";
      return true;
   }

   /* can't fit attachments into gmem */""",
    "wire PF SYSMEM control",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """   if (TU_DEBUG(GMEM)) {
      cmd->state.rp.force_render_mode_reason = "TU_DEBUG(GMEM)";
      return false;
   }

   /* This is a case where it's better to avoid GMEM, too many tiles but no HW binning possible. */""",
    """   /*
    * PF-AUDIT modes run only after Mesa's mandatory GMEM correctness gates
    * above. Mode 2 therefore means "force GMEM when legal", not "bypass
    * safety checks".
    */
   if (frane_pf_mode == 2) {
      cmd->state.rp.force_render_mode_reason =
         "TU_FRANE_PF=2: A830 PF audit forced legal GMEM";
      return false;
   }

   if (frane_pf_mode >= 3 && frane_pf_mode <= 7) {
      const struct frane_a830_pf_risk risk =
         frane_a830_pf_classify(cmd->state.pass);

      bool quarantine = false;
      switch (frane_pf_mode) {
      case 3:
         quarantine = risk.resolve;
         break;
      case 4:
         quarantine = risk.msaa;
         break;
      case 5:
         quarantine = risk.depth_stencil;
         break;
      case 6:
         quarantine = risk.store;
         break;
      case 7:
         quarantine = risk.resolve || risk.msaa || risk.depth_stencil;
         break;
      default:
         unreachable("A830 PF mode range");
      }

      if (quarantine) {
         cmd->state.rp.force_render_mode_reason =
            "TU_FRANE_PF: risky A830 GMEM class quarantined to SYSMEM";
         return true;
      }
   }

   if (TU_DEBUG(GMEM)) {
      cmd->state.rp.force_render_mode_reason = "TU_DEBUG(GMEM)";
      return false;
   }

   /* This is a case where it's better to avoid GMEM, too many tiles but no HW binning possible. */""",
    "wire PF GMEM class bisection",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static uint32_t
frane_a830_v2_flags(const struct tu_device *device)
{
   if (!frane_26320_a830_gpu(device))
      return 0;

   static const bool boost =
      debug_get_bool_option("TU_FRANE_A830_BOOST", true);
   static const bool learn =
      debug_get_bool_option("TU_FRANE_A830_LEARN", true);

   return (boost ? FRANE_A830_V2_BOOST : 0u) |
          (learn ? FRANE_A830_V2_LEARN : 0u);
}
""",
    """static uint32_t
frane_a830_v2_flags(const struct tu_device *device)
{
   if (!frane_26320_a830_gpu(device))
      return 0;

   /*
    * PF mode 8 isolates our A830 V2 selector layer while preserving the
    * underlying Mesa PROFILED path. This tells us whether the page fault
    * correlates with V2's stronger mode holds / transition pattern.
    */
   static const int64_t pf_mode =
      debug_get_num_option("TU_FRANE_PF", 0);
   if (pf_mode == 8)
      return 0;

   static const bool boost =
      debug_get_bool_option("TU_FRANE_A830_BOOST", true);
   static const bool learn =
      debug_get_bool_option("TU_FRANE_A830_LEARN", true);

   return (boost ? FRANE_A830_V2_BOOST : 0u) |
          (learn ? FRANE_A830_V2_LEARN : 0u);
}
""",
    "add V2-off PF isolation mode",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Drnas Turnip A830 V59 / Mesa ",
    "Drnas Turnip A830 PF-AUDIT V1.0 / Mesa ",
    "PF-AUDIT V1.0 display identity",
)

cmd = (V / "tu_cmd_buffer.cc").read_text()
auto = (V / "tu_autotune.cc").read_text()
dev = (V / "tu_device.cc").read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
queue = (V / "tu_queue.cc").read_text()
lrz = (V / "tu_lrz.cc").read_text()

# Exact device and one-short-variable interface.
for chip in ("0x44050000", "0x44050001", "0xffff44050000"):
    assert chip in cmd, chip
assert 'debug_get_num_option("TU_FRANE_PF", 0)' in cmd
assert 'debug_get_num_option("TU_FRANE_PF", 0)' in auto
assert "frane_a830_pf_classify" in cmd
assert "risk.resolve || risk.msaa || risk.depth_stencil" in cmd
assert "frane_pf_mode == 2" in cmd
assert "pf_mode == 8" in auto

# Do not weaken mandatory GMEM checks by moving the force-GMEM branch above
# them. The source order is part of the audit.
pos_impossible = cmd.index("Can't fit attachments into gmem")
pos_disable = cmd.index("if (cmd->state.rp.disable_gmem)")
pos_pf_gmem = cmd.index("frane_pf_mode == 2")
assert pos_impossible < pos_pf_gmem
assert pos_disable < pos_pf_gmem

# Preserve the current A830 V59 / V2 layers and the known sync/hang fixes.
assert "frane_a830_v59_lrz_gpu" in lrz
assert "frane_a830_v2_update_tail" in auto
assert "frane_a830_v2_decide" in auto
assert "FRANE_2631_POLL_READY" in kg
assert "frane_2631_deadline_ns" in kg
assert "pthread_mutex_unlock(&device->submit_mutex);" in queue

# PF-AUDIT itself must not touch the hardware-facing things we are trying to
# diagnose.
for forbidden in (
    "RB_CCU_CACHE_CNTL(",
    "VPC_ATTR_BUF_GMEM_BASE(",
    "VPC_POS_BUF_GMEM_BASE(",
    "VPC_BV_POS_BUF_GMEM_BASE(",
):
    # Existing source can contain them; this patch script never injects them.
    assert forbidden not in Path(__file__).read_text(), forbidden

assert "Drnas Turnip A830 PF-AUDIT V1.0 / Mesa " in dev

print("Drnas Turnip A830 PF-AUDIT V1.0 applied and audited", flush=True)
