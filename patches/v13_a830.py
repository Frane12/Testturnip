#!/usr/bin/env python3
"""V13 experiment based on DiskDVD A8XX-Y 6ccfee7447.

The two variants share the same pipeline and gralloc corrections.
Only a830-image-safe changes regular A830 Vulkan image compression.
The external/AHB QCOM_COMPRESSED modifier path remains untouched.
"""
from pathlib import Path
import sys

if len(sys.argv) != 2 or sys.argv[1] not in ("beta-control", "a830-image-safe"):
    raise SystemExit("usage: python3 patches/v13_a830.py {beta-control|a830-image-safe}")
variant = sys.argv[1]
root = Path("mesa")

def replace_once(file, before, after):
    path = root / file
    old = path.read_text()
    count = old.count(before)
    if count != 1:
        raise SystemExit(f"EXPECTED exactly one matching patch anchor in {file}, got {count}")
    path.write_text(old.replace(before, after, 1))

# DiskDVD's original "|| 0x44050001" is an unconditional true predicate.
# Match both normal and KGSL/no-speedbin IDs explicitly, instead.
replace_once(
    "src/freedreno/vulkan/tu_pipeline.cc",
    """   const bool is_a810 = chip_id == 0x44010000ull;
   const bool is_a812 = chip_id == 0x44010200ull;
   const bool is_a825 = chip_id == 0x44030000ull;
   const bool is_a829 = chip_id == 0x44030A20ull;
   const bool is_a830 = chip_id == 0xffff44050000 || 0x44050001;""",
    """   const bool is_a810 = chip_id == 0x44010000ull ||
                        chip_id == 0xffff44010000ull;
   const bool is_a812 = chip_id == 0x44010200ull ||
                        chip_id == 0xffff44010200ull;
   const bool is_a825 = chip_id == 0x44030000ull;
   const bool is_a829 = chip_id == 0x44030A20ull;
   const bool is_a830 = chip_id == 0xffff44050000ull ||
                        chip_id == 0xffff44050001ull ||
                        chip_id == 0x44050001ull;""",
)

# Guard the vendor handle's second integer before inspecting its UBWC flag.
# Do not guess a new gralloc ABI or globally force a format modifier.
replace_once(
    "src/util/u_gralloc/u_gralloc_fallback.c",
    """   bool ubwc = hnd->handle->data[hnd->handle->numFds + 1] & 0x08000000;
   out->modifier = ubwc ? DRM_FORMAT_MOD_QCOM_COMPRESSED : DRM_FORMAT_MOD_LINEAR;""",
    """   if (hnd->handle->numInts >= 2) {
      bool ubwc = hnd->handle->data[hnd->handle->numFds + 1] & 0x08000000;
      out->modifier = ubwc ? DRM_FORMAT_MOD_QCOM_COMPRESSED : DRM_FORMAT_MOD_LINEAR;
   }""",
)

if variant == "a830-image-safe":
    # Diagnostic for wild purple/blue corrupted render targets on A830.
    # Equivalent to NOUBWC only for *ordinary A830 Vulkan images*.
    # Imported Android buffers explicitly marked QCOM_COMPRESSED MUST retain
    # their actual modifier/UBWC layout (and may be force-enabled downstream).
    # Keep tiling enabled. Keep GMEM/SYSMEM user-selectable via TU_DEBUG.
    replace_once(
        "src/freedreno/vulkan/tu_image.cc",
        """   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* Layout computation begins here */""",
        """   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* V13 A830 IMAGE-SAFE experiment: avoid compressed layouts for ordinary
    * Vulkan images. External QCOM_COMPRESSED Android buffers are untouched.
    * This tests whether A830 UBWC image/metadata handling causes corruption.
    */
   const uint64_t image_chip_id = device->physical_device->dev_id.chip_id;
   const bool image_is_a830 =
      image_chip_id == 0xffff44050000ull ||
      image_chip_id == 0xffff44050001ull ||
      image_chip_id == 0x44050001ull;
   if (image_is_a830 && modifier != DRM_FORMAT_MOD_QCOM_COMPRESSED)
      ubwc_enabled = false;

   /* Layout computation begins here */""",
    )

print(f"V13 patches applied: {variant}")
