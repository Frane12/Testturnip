from pathlib import Path

def replace_once(path: Path, old: str, new: str, label: str):
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    path.write_text(text.replace(old, new, 1))

lrz = Path("mesa/src/freedreno/vulkan/tu_lrz.cc")

replace_once(
    lrz,
    """TU_GENX(tu_lrz_flush_valid_at_suspending_rp_boundary);

static bool
tu_has_potential_stencil_feedback_loop""",
    """TU_GENX(tu_lrz_flush_valid_at_suspending_rp_boundary);

static bool
frane_a830_v59_lrz_gpu(const struct tu_cmd_buffer *cmd)
{
   if (!cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t id = cmd->device->physical_device->dev_id.chip_id;
   return id == UINT64_C(0x44050000) ||
          id == UINT64_C(0x44050001) ||
          id == UINT64_C(0xffff44050000);
}

static bool
tu_has_potential_stencil_feedback_loop""",
    "lrz helper",
)

replace_once(
    lrz,
    """   VkCompareOp depth_compare_op =
      cmd->vk.dynamic_graphics_state.ds.depth.compare_op;

   struct __GRAS_LRZ_CNTL gras_lrz_cntl = { 0 };""",
    """   VkCompareOp depth_compare_op =
      cmd->vk.dynamic_graphics_state.ds.depth.compare_op;

   /* A830 V59/S2-D2: one exact-device lookup reused by LRZ decisions. */
   const bool frane_a830_v59 = frane_a830_v59_lrz_gpu(cmd);

   struct __GRAS_LRZ_CNTL gras_lrz_cntl = { 0 };""",
    "lrz device flag",
)

replace_once(
    lrz,
    """   if (disable_lrz_due_to_fs) {
      if (cmd->state.lrz.prev_direction != TU_LRZ_UNKNOWN || !cmd->state.lrz.gpu_dir_tracking) {
         perf_debug(cmd->device, "Skipping LRZ due to FS");
         temporary_disable_lrz = true;
      } else {
         tu_lrz_invalidate(cmd, "FS writes depth or has side-effects (TODO: fix for gpu-direction-tracking case)");
      }
   }""",
    """   if (disable_lrz_due_to_fs) {
      /*
       * A830 V59 LRZ-KEEP: if this exact A830 draw cannot write Z, the FS
       * hazard cannot alter depth/LRZ contents. Keep LRZ valid and only skip
       * LRZ for this draw. Preserve upstream behavior for real depth writes.
       */
      if ((frane_a830_v59 && !z_write_enable) ||
          cmd->state.lrz.prev_direction != TU_LRZ_UNKNOWN ||
          !cmd->state.lrz.gpu_dir_tracking) {
         perf_debug(cmd->device, "Skipping LRZ due to FS");
         temporary_disable_lrz = true;
      } else {
         tu_lrz_invalidate(cmd, "FS writes depth or has side-effects (TODO: fix for gpu-direction-tracking case)");
      }
   }""",
    "lrz fs hazard",
)

replace_once(
    lrz,
    """      if (frag_may_be_killed_by_stencil) {
         tu_lrz_disable_write_for_rp(cmd, "Stencil may kill fragments");
      }""",
    """      if (frag_may_be_killed_by_stencil) {
         /*
          * A830 V59 LRZ-CLEAN: with Z writes disabled, LRZ writes are already
          * disabled for this draw. Avoid making that state sticky for the RP
          * on A830; upstream behavior remains unchanged elsewhere.
          */
         if (!frane_a830_v59 || z_write_enable)
            tu_lrz_disable_write_for_rp(cmd, "Stencil may kill fragments");
      }""",
    "lrz stencil",
)

sub = Path("mesa/src/freedreno/vulkan/tu_suballoc.cc")

replace_once(
    sub,
    """#include "tu_suballoc.h"
""",
    """#include "tu_suballoc.h"
#include "tu_device.h"
#include "util/os_misc.h"
#include <string.h>
""",
    "suballoc includes",
)

replace_once(
    sub,
    """   if (result != VK_SUCCESS) {
      tu_bo_finish(suballoc->dev, suballoc->bo);
      suballoc->bo = NULL;
      return VK_ERROR_OUT_OF_HOST_MEMORY;
   }""",
    """   if (result != VK_SUCCESS) {
      tu_bo_finish(suballoc->dev, suballoc->bo);
      suballoc->bo = NULL;
      suballoc->next_offset = 0;
      return result;
   }""",
    "suballoc map failure",
)

replace_once(
    sub,
    """   if (p_atomic_read(&bo->bo->refcnt) == 1 && !suballoc->cached_bo) {
      suballoc->cached_bo = bo->bo;
      return;
   }""",
    """   /* A830 lean-memory policy: keep the normal recycled BO fast path,
    * but do not retain oversized autotune BOs. This only runs when this
    * caller owns the final reference, so no live/submitted BO is freed early.
    */
   static const bool frane_lean_cache = []() {
      const char *env = os_get_option("TU_A830_LEAN_CACHE");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t id = suballoc->dev->physical_device->dev_id.chip_id;
   const bool frane_a830 =
      id == 0x44050001ull || id == 0x44050000ull ||
      id == 0xffff44050000ull;
   static const bool frane_a810_lean_cache = []() {
      const char *env = os_get_option("TU_A810_LEAN_CACHE");
      return env && strcmp(env, "1") == 0;
   }();
   const bool frane_a810 =
      id == 0x44010000ull || id == 0xffff44010000ull;
   const bool drop_oversize_autotune =
      ((frane_lean_cache && frane_a830) ||
       (frane_a810_lean_cache && frane_a810)) &&
      strcmp(suballoc->name, "autotune_suballoc") == 0 &&
      bo->bo->size > 64 * 1024;

   if (p_atomic_read(&bo->bo->refcnt) == 1 &&
       !suballoc->cached_bo && !drop_oversize_autotune) {
      suballoc->cached_bo = bo->bo;
      return;
   }""",
    "suballoc lean cache",
)

print("A830 upstream LRZ/suballocator rebase applied")
