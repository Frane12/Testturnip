#!/usr/bin/env python3
"""A830 V18 diagnostic: isolate internally allocated depth/stencil UBWC.

This is an A/B probe for camera-relative square lighting artifacts, NOT
an established root-cause fix. Keep color UBWC, GMEM and all V16 RAM
policies unchanged. Explicit external modifiers must never be overridden.
TU_A830_SAFE_DEPTH_UBWC=0 restores V16 image layout after relaunch.
"""
from pathlib import Path
p=Path("mesa/src/freedreno/vulkan/tu_image.cc")
s=p.read_text()
old="""   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* Layout computation begins here */"""
new="""   /* V18: isolate the depth/stencil compression path on A830 only.
    * External modifier/AHB layouts must remain producer-compatible.
    * GMEM, color UBWC, tile geometry and buffer lifetime are unchanged.
    */
   static const bool frane_a830_safe_depth = []() {
      const char *env = os_get_option("TU_A830_SAFE_DEPTH_UBWC");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t frane_depth_chip = device->physical_device->dev_id.chip_id;
   const bool frane_depth_a830 =
      frane_depth_chip == 0x44050001ull ||
      frane_depth_chip == 0x44050000ull ||
      frane_depth_chip == 0xffff44050000ull;
   if (frane_depth_a830 && frane_a830_safe_depth &&
       modifier == DRM_FORMAT_MOD_INVALID &&
       vk_format_is_depth_or_stencil(image->vk.format))
      ubwc_enabled = false;

   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* Layout computation begins here */"""
assert s.count(old)==1, f"image anchor mismatch {s.count(old)}"
p.write_text(s.replace(old,new,1))
print("A830 V18 depth UBWC A/B probe applied (default ON, opt-out =0)",flush=True)
