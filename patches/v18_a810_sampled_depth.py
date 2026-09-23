#!/usr/bin/env python3
"""A810 V18 opt-in depth-as-texture diagnostic, based on field-tested V17.

TU_A810_SAMPLED_DEPTH_DIAG=1 disables UBWC ONLY on internal depth/stencil
images that are sampled (or input attachments), not all depth images.
V17 TU_A810_SAFE_DEPTH_UBWC=1 remains a separate, broader experiment.
Explicit external DRM modifiers are never overridden. This does not claim
to fix the cause of camera-relative lighting artifacts.
"""
from pathlib import Path
p=Path("mesa/src/freedreno/vulkan/tu_image.cc")
s=p.read_text()
old="""   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* Layout computation begins here */"""
new="""   /* V18 A810: A/B probe for sampled depth in screen-space lighting.
    * Keep the V17 broad depth experiment independent and default OFF.
    * Preserve external/AHB layouts, color UBWC and GMEM behavior.
    */
   static const bool frane_sampled_depth_diag = []() {
      const char *env = os_get_option("TU_A810_SAMPLED_DEPTH_DIAG");
      return env && strcmp(env, "1") == 0;
   }();
   const uint64_t frane_sampled_chip =
      device->physical_device->dev_id.chip_id;
   const bool frane_sampled_a810 =
      frane_sampled_chip == 0x44010000ull ||
      frane_sampled_chip == 0xffff44010000ull;
   if (frane_sampled_a810 && frane_sampled_depth_diag &&
       modifier == DRM_FORMAT_MOD_INVALID &&
       vk_format_is_depth_or_stencil(image->vk.format) &&
       (pCreateInfo->usage &
        (VK_IMAGE_USAGE_SAMPLED_BIT |
         VK_IMAGE_USAGE_INPUT_ATTACHMENT_BIT)))
      ubwc_enabled = false;

   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* Layout computation begins here */"""
assert s.count(old)==1, f"V18 depth source anchor: {s.count(old)}"
p.write_text(s.replace(old,new,1))
print("PASS V18 A810 sampled-depth opt-in diagnostic",flush=True)
