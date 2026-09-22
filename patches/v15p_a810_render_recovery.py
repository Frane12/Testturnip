#!/usr/bin/env python3
"""V15-P A810 RENDER RECOVERY: diagnose missing images before GMEM tuning.

Base V15-O only; leave all tested A830 branches untouched.

 - Apply whitebelyash's 1-slice A810 0x78000 GMEM initial-offset guard
   from tu_gen8.patch to prevent underflow in its ~576 KiB cache.
 - Explicitly install documented A810 small-GMEM and cache geometry props;
   do not inherit A830's 3-slice geometry.
 - Default A810 TU_A810_GMEM_PROFILE to 0 and prefer_sysmem.
   TU_DEBUG=sysmem is still the *strict* diagnostic override.
 - Default A810 lean-budget/BO-cache experiments OFF while investigating.
 - Profiles 1 and 2 remain opt-in experiments; do not claim known-good GMEM.

No BO premature freeing, no texture memory pressure "cleaner", no disabled
UBWC across the board or Qualcomm proprietary code.
"""
from pathlib import Path

def replace_once(path, old, new):
    p=Path("mesa")/path
    s=p.read_text()
    n=s.count(old)
    if n!=1: raise SystemExit(f"V15-P upstream drift ({path}) matches={n}: {old[:110]!r}")
    p.write_text(s.replace(old,new,1))

# This exact underflow was documented by whitebelyash in gen8.
p=Path("mesa/src/freedreno/common/fd6_gmem_cache.h")
s=p.read_text()
old="if (info->chip >= 8)"
new="if (info->chip >= 8 && info->num_slices > 1)"
if s.count(old)==1:
    p.write_text(s.replace(old, new, 1))
elif s.count(new)==1:
    print("V15-P: offset guard already present upstream")
else:
    raise SystemExit("V15-P: couldn't prove A810 initial GMEM-offset guard")

# GPUProps from the A810 profile in whitebelyash/mesa-tu8; the existing
# A810-only has_fs_tex_prefetch=False remains untouched.
replace_once(
    "src/freedreno/common/freedreno_devices.py",
    """            gmem_vpc_bv_pos_buf_size = 20480,
            # This is possibly also needed for a830""",
    """            gmem_vpc_bv_pos_buf_size = 20480,
            # V15-P: A810 has a much smaller one-slice GMEM/cache than A830.
            # Explicit A810-only layout based on whitebelyash/mesa-tu8;
            # no forced GMEM use and no change to any A830 GPU properties.
            gmem_size = 576 * 1024,
            sysmem_vpc_attr_buf_size = 131072,
            sysmem_vpc_pos_buf_size = 65536,
            sysmem_vpc_bv_pos_buf_size = 32768,
            sysmem_ccu_color_cache_fraction = CCUColorCacheFraction.FULL.value,
            sysmem_per_ccu_color_cache_size = 64 * 1024,
            sysmem_ccu_depth_cache_fraction = CCUColorCacheFraction.THREE_QUARTER.value,
            sysmem_per_ccu_depth_cache_size = 64 * 1024,
            gmem_ccu_color_cache_fraction = CCUColorCacheFraction.EIGHTH.value,
            gmem_per_ccu_color_cache_size = 32 * 1024,
            gmem_ccu_depth_cache_fraction = CCUColorCacheFraction.FULL.value,
            gmem_per_ccu_depth_cache_size = 48 * 1024,
            # This is possibly also needed for a830""",
)

replace_once(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      return 1u;
   }();
   return profile;
}""",
    """      /* Safe A810 control: no custom GMEM until SYSMEM textures work. */
      return 0u;
   }();
   return profile;
}""",
)
replace_once(
    "src/freedreno/vulkan/tu_autotune.cc",
    """      else if (frane_a830_smart_gmem(device))
         /* Allow carefully gated Mesa bandwidth autotuning on A830, while""",
    """      else if (frane_a810_gpu(device) && frane_a810_gmem_profile() == 0)
         /* Prefer SYSMEM for A810 by default; TU_DEBUG=sysmem strictly
          * enforces it for diagnosis. Explicit user algorithm still wins.
          */
         algo_strv = "prefer_sysmem";
      else if (frane_a830_smart_gmem(device))
         /* Allow carefully gated Mesa bandwidth autotuning on A830, while""",
)
replace_once(
    "src/freedreno/vulkan/tu_device.cc",
    """      const char *env = os_get_option("TU_A810_LEAN_BUDGET");
      return !env || strcmp(env, "0") != 0;""",
    """      const char *env = os_get_option("TU_A810_LEAN_BUDGET");
      return env && strcmp(env, "1") == 0;""",
)
replace_once(
    "src/freedreno/vulkan/tu_suballoc.cc",
    """      const char *env = os_get_option("TU_A810_LEAN_CACHE");
      return !env || strcmp(env, "0") != 0;""",
    """      const char *env = os_get_option("TU_A810_LEAN_CACHE");
      return env && strcmp(env, "1") == 0;""",
)
print("V15-P A810: 1-slice offset fix; A810 geometry; SYSMEM-first; lean A810 opt-in")
