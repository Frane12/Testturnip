#!/usr/bin/env python3
"""V15-B: isolated A830 image UBWC experiment on upstream Mesa 26.1.4.

Upstream stores the UBWC decision in image->ubwc_enabled rather than the
DiskDVD local ubwc_enabled variable. Fail closed on unexpected source.
"""
from pathlib import Path

path = Path("mesa/src/freedreno/vulkan/tu_image.cc")
source = path.read_text()
anchor = """   if (TU_DEBUG(NOUBWC)) {
      image->ubwc_enabled = false;
   }
"""
if source.count(anchor) != 1:
    raise SystemExit(
        f"Expected exactly one upstream image->ubwc_enabled NOUBWC guard, "
        f"got {source.count(anchor)}; no patch applied"
    )
addition = """
   /* V15-B A830 IMAGE-SAFE diagnostic. Keep upstream Mesa 26.1.4.
    * The external compressed modifier is handled later in image layout.
    */
   const uint64_t frane_chip_id = device->physical_device->dev_id.chip_id;
   if (frane_chip_id == 0xffff44050000ull ||
       frane_chip_id == 0xffff44050001ull ||
       frane_chip_id == 0x44050001ull)
      image->ubwc_enabled = false;
"""
path.write_text(source.replace(anchor, anchor + addition, 1))
print("V15-B: upstream Mesa 26.1.4 A830 image UBWC patch applied")
