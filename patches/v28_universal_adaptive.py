#!/usr/bin/env python3
"""V28: universal adaptive profiler + stable cross-process RP identity.

Built on V26. Keeps all existing A810-specific safety/power workarounds scoped
to A810, while making the PROFILED learning/cache layer capability-gated and
usable across Turnip generations. Ports Mesa commit af16b1c's stable image-id
RP hash so persistent history can survive process restarts.
"""
from pathlib import Path

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(path, old, new, label):
    p = ROOT / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V28 source drift: {label}: expected 1 anchor, saw {n}: {old[:120]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"V28 PASS {label}", flush=True)

# ---------------------------------------------------------------------------
# 1) Port upstream stable image identities (Mesa af16b1c).
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_image.h",
'''   /* Maximum width/height of tiles for use with this image, or ~0 if no constraints. */
   uint32_t max_tile_w_constraint_fdm;
   uint32_t max_tile_h_constraint_fdm;
};
VK_DEFINE_NONDISP_HANDLE_CASTS(tu_image, vk.base, VkImage, VK_OBJECT_TYPE_IMAGE)

template <chip CHIP>
VkResult
tu_image_init(struct tu_device *device, struct tu_image *image,
              const VkImageCreateInfo *pCreateInfo, uint64_t modifier,
              const VkSubresourceLayout *plane_layouts);''',
'''   /* Maximum width/height of tiles for use with this image, or ~0 if no constraints. */
   uint32_t max_tile_w_constraint_fdm;
   uint32_t max_tile_h_constraint_fdm;

   /* Stable identity used by the autotuner RP hash. 0 means no identity. */
   uint64_t id;
};
VK_DEFINE_NONDISP_HANDLE_CASTS(tu_image, vk.base, VkImage, VK_OBJECT_TYPE_IMAGE)

enum tu_image_id_mode {
   TU_IMAGE_ID_NONE,
   TU_IMAGE_ID_ASSIGN,
   TU_IMAGE_ID_INTERNAL,
};

#define TU_IMAGE_ID_INTERNAL_ID UINT64_MAX

template <chip CHIP>
VkResult
tu_image_init(struct tu_device *device, struct tu_image *image,
              const VkImageCreateInfo *pCreateInfo, uint64_t modifier,
              const VkSubresourceLayout *plane_layouts,
              enum tu_image_id_mode id_mode);''',
"stable image identity declaration")

edit("src/freedreno/vulkan/tu_device.h",
'''   uint32_t vis_stream_count;
   uint32_t vis_stream_size;
};
VK_DEFINE_HANDLE_CASTS(tu_device, vk.base, VkDevice, VK_OBJECT_TYPE_DEVICE)''',
'''   uint32_t vis_stream_count;
   uint32_t vis_stream_size;

   /* Monotonic image identity; deterministic for the same API creation order. */
   uint64_t next_image_id;
};
VK_DEFINE_HANDLE_CASTS(tu_device, vk.base, VkDevice, VK_OBJECT_TYPE_DEVICE)''',
"device image-id counter")

edit("src/freedreno/vulkan/tu_image.cc",
'''#include "util/format/u_format.h"
#include "util/u_debug.h"''',
'''#include "util/format/u_format.h"
#include "util/u_atomic.h"
#include "util/u_debug.h"''',
"atomic helper include")

edit("src/freedreno/vulkan/tu_image.cc",
'''tu_image_init(struct tu_device *device, struct tu_image *image,
              const VkImageCreateInfo *pCreateInfo, uint64_t modifier,
              const VkSubresourceLayout *plane_layouts)
{
   bool ubwc_enabled = true;''',
'''tu_image_init(struct tu_device *device, struct tu_image *image,
              const VkImageCreateInfo *pCreateInfo, uint64_t modifier,
              const VkSubresourceLayout *plane_layouts,
              enum tu_image_id_mode id_mode)
{
   switch (id_mode) {
   case TU_IMAGE_ID_ASSIGN:
      image->id = p_atomic_inc_return(&device->next_image_id);
      break;
   case TU_IMAGE_ID_INTERNAL:
      image->id = TU_IMAGE_ID_INTERNAL_ID;
      break;
   case TU_IMAGE_ID_NONE:
      break;
   }

   bool ubwc_enabled = true;''',
"assign stable image identities")

edit("src/freedreno/vulkan/tu_image.cc",
'''   result = TU_CALLX(dev, tu_image_init)(
      dev, img, img->vk.android_deferred_create_info,
      eci.drmFormatModifier, a_plane_layouts);''',
'''   result = TU_CALLX(dev, tu_image_init)(
      dev, img, img->vk.android_deferred_create_info,
      eci.drmFormatModifier, a_plane_layouts, TU_IMAGE_ID_ASSIGN);''',
"deferred Android image identity")

edit("src/freedreno/vulkan/tu_image.cc",
'''   result = TU_CALLX(device, tu_image_init)(device, image, pCreateInfo,
                                             modifier, plane_layouts);''',
'''   result = TU_CALLX(device, tu_image_init)(device, image, pCreateInfo,
                                             modifier, plane_layouts,
                                             TU_IMAGE_ID_ASSIGN);''',
"normal image identity")

for label, old in [
    ("memory requirement temp identity", '''   TU_CALLX(device, tu_image_init)(device, &image, pInfo->pCreateInfo, DRM_FORMAT_MOD_INVALID, NULL);

   tu_get_image_memory_requirements'''),
    ("sparse requirement temp identity", '''   TU_CALLX(device, tu_image_init)(device, &image, pInfo->pCreateInfo, DRM_FORMAT_MOD_INVALID, NULL);

   tu_get_image_sparse_memory_requirements'''),
    ("subresource temp identity", '''   TU_CALLX(device, tu_image_init)(device, &image, pInfo->pCreateInfo, DRM_FORMAT_MOD_INVALID, NULL);

   tu_get_image_subresource_layout'''),
]:
    new = old.replace("DRM_FORMAT_MOD_INVALID, NULL);",
                      "DRM_FORMAT_MOD_INVALID, NULL, TU_IMAGE_ID_NONE);")
    edit("src/freedreno/vulkan/tu_image.cc", old, new, label)

edit("src/freedreno/vulkan/tu_device.cc",
'''      result = TU_CALLX(device, tu_image_init)(
         device, mem->image, mem->image->vk.android_deferred_create_info,
         eci.drmFormatModifier, a_plane_layouts);''',
'''      result = TU_CALLX(device, tu_image_init)(
         device, mem->image, mem->image->vk.android_deferred_create_info,
         eci.drmFormatModifier, a_plane_layouts, TU_IMAGE_ID_ASSIGN);''',
"deferred allocation image identity")

edit("src/freedreno/vulkan/tu_device.cc",
'''      TU_CALLX(device, tu_image_init)(device, &images[i], &image_info, DRM_FORMAT_MOD_INVALID, NULL);''',
'''      TU_CALLX(device, tu_image_init)(device, &images[i], &image_info, DRM_FORMAT_MOD_INVALID, NULL,
                                      TU_IMAGE_ID_INTERNAL);''',
"MSRTSS internal stable identity")

# Stable RP hash: upstream af16b1c.
edit("src/freedreno/vulkan/tu_autotune.cc",
'''   struct PACKED packed_att_properties {
      uint64_t iova;
      bool load;
      bool store;
      bool load_stencil;
      bool store_stencil;
   };''',
'''   struct PACKED packed_att_properties {
      uint64_t img_id;
      uint32_t view_offset;
      bool load;
      bool store;
      bool load_stencil;
      bool store_stencil;
   };''',
"stable RP attachment key layout")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''      for (unsigned i = 0; i < pass->attachment_count; i++) {
         packed_att_properties props = {
            .iova = cmd->state.attachments[i]->image->iova + cmd->state.attachments[i]->view.offset,
            .load = pass->attachments[i].load,''',
'''      for (unsigned i = 0; i < pass->attachment_count; i++) {
         assert(cmd->state.attachments[i]->image->id != 0);
         packed_att_properties props = {
            .img_id = cmd->state.attachments[i]->image->id,
            .view_offset = cmd->state.attachments[i]->view.offset,
            .load = pass->attachments[i].load,''',
"stable RP image id + view offset")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''   constexpr size_t STACK_MAX_DATA_COUNT = 3 + (5 * 3); /* in u32 units. */''',
'''   constexpr size_t STACK_MAX_DATA_COUNT =
      3 + (5 * (sizeof(packed_att_properties) / sizeof(uint32_t)));''',
"RP hash stack sizing")

# ---------------------------------------------------------------------------
# 2) Make the V22/V24 lean PROFILED path reusable across Turnip GPUs.
#    A830 retains its existing smart-GMEM default because that branch runs
#    before this generic fallback; explicit TU_AUTOTUNE_ALGO always wins.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_autotune.cc",
'''static bool
frane_a810_gpu(const struct tu_device *device)''',
'''static bool
frane_v28_universal_profiled(const struct tu_device *device)
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_UNIVERSAL_PROFILED", true);
   return enabled && device && device->physical_device &&
          device->physical_device->gmem_size > 0 &&
          device->physical_device->info->chip >= A6XX;
}

static bool
frane_a810_gpu(const struct tu_device *device)''',
"universal capability gate")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''static bool
frane_a810_v24_fastpath()
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_V24_FASTPATH", true);
   return enabled;
}''',
'''static bool
frane_a810_v24_fastpath()
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_FASTPATH",
         debug_get_bool_option("TU_A810_V24_FASTPATH", true));
   return enabled;
}''',
"generic fastpath env with A810 compatibility")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''static bool
frane_a810_lean_profiled()
{
   static const bool enabled = debug_get_bool_option("TU_A810_LEAN_PROFILED", true);
   return enabled;
}''',
'''static bool
frane_a810_lean_profiled()
{
   static const bool enabled =
      debug_get_bool_option("TU_FRANE_LEAN_PROFILED",
         debug_get_bool_option("TU_A810_LEAN_PROFILED", true));
   return enabled;
}''',
"generic lean-profiled env with A810 compatibility")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''static uint32_t
frane_a810_sample_interval()
{
   static const uint32_t interval = frane_profiled_sample_interval(
      debug_get_num_option("TU_A810_PROFILED_SAMPLE_INTERVAL", 8));
   return interval;
}''',
'''static uint32_t
frane_a810_sample_interval()
{
   static const uint32_t interval = frane_profiled_sample_interval(
      debug_get_num_option("TU_FRANE_PROFILED_SAMPLE_INTERVAL",
         debug_get_num_option("TU_A810_PROFILED_SAMPLE_INTERVAL", 8)));
   return interval;
}''',
"generic sample interval env with A810 compatibility")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''      else if (device->instance->drirc.perf.autotune_algo)
         algo_strv = device->instance->drirc.perf.autotune_algo;

      if (!algo_strv.empty()) {''',
'''      else if (device->instance->drirc.perf.autotune_algo)
         algo_strv = device->instance->drirc.perf.autotune_algo;
      else if (frane_v28_universal_profiled(device))
         algo_strv = "profiled";

      if (!algo_strv.empty()) {''',
"generic PROFILED default after explicit/drirc/GPU-specific policies")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''         frane_a810_gpu(device) && frane_a810_lean_profiled() &&
         !config.test(metric_flag::TS_TILE) ? 0 : tile_count;''',
'''         frane_v28_universal_profiled(device) && frane_a810_lean_profiled() &&
         !config.test(metric_flag::TS_TILE) ? 0 : tile_count;''',
"generic lean timestamp allocation")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''   if (frane_a810_gpu(device) && frane_a810_lean_profiled() &&
       config.is_enabled(algorithm::PROFILED) &&''',
'''   if (frane_v28_universal_profiled(device) && frane_a810_lean_profiled() &&
       config.is_enabled(algorithm::PROFILED) &&''',
"generic one-time-CB sampled profiler")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''   if (frane_a810_gpu(device) && frane_a810_v24_fastpath() &&
       active_batches.empty())''',
'''   if (frane_v28_universal_profiled(device) && frane_a810_v24_fastpath() &&
       active_batches.empty())''',
"generic empty-results fastpath")

# ---------------------------------------------------------------------------
# 3) Universal persistent prior. Keep it weak (35/65), continuously remeasure,
#    and invalidate across GPU/driver changes using device/cache UUIDs.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_autotune.cc",
'''bool
tu_autotune::frane_profile_key(uint64_t rp_hash, cache_key key) const
{
   if (!frane_a810_gpu(device) ||
       !debug_get_bool_option("TU_A810_PROFILE_CACHE", true) ||
       !device->physical_device->vk.disk_cache)
      return false;
   const char *name = debug_get_option("TU_A810_PROFILE_ID", nullptr);
   if (!name || !*name)
      name = device->instance->vk.app_info.app_name;
   /* Generic or absent app names cannot safely isolate games. Supply
    * TU_A810_PROFILE_ID=<game> when the translation layer uses one. */
   if (!name || !*name || !strcmp(name, "DXVK") || !strcmp(name, "Wine"))
      return false;
   std::string input = std::string("frane-a810-v26:") + name + ":" +
                       std::to_string(rp_hash);
   disk_cache_compute_key(device->physical_device->vk.disk_cache, input.data(), input.size(), key);
   return true;
}''',
'''bool
tu_autotune::frane_profile_key(uint64_t rp_hash, cache_key key) const
{
   const bool legacy_enabled =
      debug_get_bool_option("TU_A810_PROFILE_CACHE", true);
   if (!debug_get_bool_option("TU_FRANE_PROFILE_CACHE", legacy_enabled) ||
       !frane_v28_universal_profiled(device) ||
       !device->physical_device->vk.disk_cache)
      return false;

   const char *name = debug_get_option("TU_FRANE_PROFILE_ID", nullptr);
   if (!name || !*name)
      name = debug_get_option("TU_A810_PROFILE_ID", nullptr);
   if (!name || !*name)
      name = device->instance->vk.app_info.app_name;

   /* Translation layers often expose only a generic app name. Do not allow
    * unrelated games to share a persistent prior unless the user supplies ID.
    */
   if (!name || !*name || !strcmp(name, "DXVK") || !strcmp(name, "Wine"))
      return false;

   std::string input = std::string("frane-universal-v28:") + name + ":" +
                       std::to_string(rp_hash);
   /* Separate different GPUs and automatically invalidate when Mesa's cache
    * UUID changes due to a driver build/config change.
    */
   input.append((const char *)device->physical_device->device_uuid, VK_UUID_SIZE);
   input.append((const char *)device->physical_device->cache_uuid, VK_UUID_SIZE);

   disk_cache_compute_key(device->physical_device->vk.disk_cache,
                          input.data(), input.size(), key);
   return true;
}''',
"universal versioned persistent profile key")

edit("src/freedreno/vulkan/tu_autotune.cc",
'''            if (frane_a810_gpu(at.device) &&
                at_config.is_enabled(algorithm::PROFILED) &&
                !at_config.is_enabled(algorithm::PROFILED_IMM) &&''',
'''            if (frane_v28_universal_profiled(at.device) &&
                at_config.is_enabled(algorithm::PROFILED) &&
                !at_config.is_enabled(algorithm::PROFILED_IMM) &&''',
"generic persistent profile save gate")

# Identity in HUD / Vulkan driver string.
edit("src/freedreno/vulkan/tu_device.cc",
     "Frane A810 V26-ADAPTIVE-CACHE / Mesa ",
     "Frane V28-UNIVERSAL-ADAPTIVE / Mesa ",
     "V28 driver identity")

print("V28 universal adaptive profiler + stable cross-process RP key applied", flush=True)
