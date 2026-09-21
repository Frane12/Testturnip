#!/usr/bin/env python3
"""V15-B: port only V13 A830 IMAGE-SAFE UBWC decision onto clean Mesa 26.1.4.

No DiskDVD source, pipeline rewrites, gralloc ABI assumptions, or global NOUBWC.
Fail closed if the upstream source layout differs from the expected anchor.
"""
from pathlib import Path

path = Path("mesa/src/freedreno/vulkan/tu_image.cc")
source = path.read_text()
anchor = """   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* Layout computation begins here */"""
replacement = """   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* V15-B: isolated port of Frane V13 IMAGE-SAFE onto clean Mesa 26.1.4.
    * Disable UBWC only for ordinary A830 Vulkan images; preserve explicit
    * QCOM_COMPRESSED imported AHB buffers and leave tiling unchanged.
    */
   const uint64_t image_chip_id = device->physical_device->dev_id.chip_id;
   const bool image_is_a830 =
      image_chip_id == 0xffff44050000ull ||
      image_chip_id == 0xffff44050001ull ||
      image_chip_id == 0x44050001ull;
   if (image_is_a830 && modifier != DRM_FORMAT_MOD_QCOM_COMPRESSED)
      ubwc_enabled = false;

   /* Layout computation begins here */"""
count = source.count(anchor)
if count != 1:
    raise SystemExit(f"Expected exactly one Mesa 26.1.4 UBWC/layout anchor, got {count}; no patch applied")
path.write_text(source.replace(anchor, replacement, 1))
print("V15-B: clean Mesa 26.1.4 + isolated V13 A830 IMAGE-SAFE applied")
