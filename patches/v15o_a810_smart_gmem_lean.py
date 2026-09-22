#!/usr/bin/env python3
"""V15-O A810: build on V15-N, independently gated A810 GMEM + lean memory.

Recognise upstream 0xffff44010000 and KGSL 0x44010000 aliases.
Do not spoof A830, overwrite its policies or edit 576-KiB GMEM hardware
layout, CCU/cache registers, UBWC, BO lifetimes or submission fences.
Only conservatively select Mesa's existing safe GMEM render mode from the
previously observed attachment/draw bandwidth and A810-specific tile count.

TU_A810_GMEM_PROFILE=0: original non-smart Mesa default/policy (use
                           TU_AUTOTUNE_ALGO=prefer_sysmem for sysmem A/B)
TU_A810_GMEM_PROFILE=1: default, cautious cost-based GMEM
TU_A810_GMEM_PROFILE=2: experimental, moderately more GMEM candidates
TU_A810_LEAN_BUDGET=0: V15-G advisory 70% (default A810 60%)
TU_A810_LEAN_CACHE=0: V15-N free-autotune-BO cache behavior disabled
TU_A830_*: unchanged for A830.

A810 small physical GMEM (~576 KiB) requires caution. A build cannot prove
GMEM runtime safety, image correctness or actual RAM savings.
"""
from pathlib import Path

def edit(path: str, old: str, new: str):
    p = Path("mesa") / path
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V15-O patch drift in {path}: matches={n}: {old[:95]!r}")
    p.write_text(s.replace(old, new, 1))

# On Mesa 26.1.4 original Adreno 810 entry has the sysmem/drm chip ID but
# on some Android KGSL devices this short ID is reported instead.
edit(
    "src/freedreno/common/freedreno_devices.py",
    'GPUId(chip_id=0xffff44010000, name="Adreno (TM) 810"),',
    'GPUId(chip_id=0xffff44010000, name="Adreno (TM) 810"),\n'
    '       GPUId(chip_id=0x44010000, name="Adreno (TM) 810"),',
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """static bool
frane_a830_smart_gmem(const struct tu_device *device)""",
    """/* 576-KiB GMEM A810, exact chip-id scope; never pretend it is A830. */
static bool
frane_a810_gpu(const struct tu_device *device)
{
   const uint64_t id = device->physical_device->dev_id.chip_id;
   return id == 0x44010000ull || id == 0xffff44010000ull;
}

static uint32_t
frane_a810_gmem_profile(void)
{
   static const uint32_t profile = []() {
      const char *env = os_get_option("TU_A810_GMEM_PROFILE");
      if (env && strcmp(env, "0") == 0)
         return 0u;
      if (env && strcmp(env, "2") == 0)
         return 2u;
      return 1u;
   }();
   return profile;
}

static bool
frane_a830_smart_gmem(const struct tu_device *device)""",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """   return enabled &&
      (id == 0x44050001ull || id == 0x44050000ull ||
       id == 0xffff44050000ull);""",
    """   const bool a830 = enabled &&
      (id == 0x44050001ull || id == 0x44050000ull ||
       id == 0xffff44050000ull);
   return a830 ||
      (frane_a810_gpu(device) && frane_a810_gmem_profile() != 0);
""".rstrip(),
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """                                   bool a830_smart_gmem,
                                   uint32_t a830_memory_tier)""",
    """                                   bool a830_smart_gmem,
                                   uint32_t a830_memory_tier,
                                   bool is_a810)""",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            const bool measured_candidate =
               a830_memory_tier != 0 &&
               rp_state->drawcall_count >= 10 &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= 1920u * 1080u &&
               approx_tiles <= 12 &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;""",
    """            /* A810 has only ~576 KiB GMEM. Require previous samples,
             * smaller RP, fewer full-layout tiles and clear predicted
             * savings before opting in. Profile 2 is test-only, never
             * overrides Mesa's hardware safety/correctness conditions.
             */
            const uint32_t a810_profile =
               is_a810 ? frane_a810_gmem_profile() : 0u;
            const uint32_t min_draws =
               is_a810 ? (a810_profile == 2 ? 10u : 12u) : 10u;
            const uint64_t max_tiles =
               is_a810 ? (a810_profile == 2 ? 16u : 8u) : 12u;
            const uint32_t max_pixels =
               is_a810 ? (a810_profile == 2 ? 1600u * 900u
                                             : 1280u * 800u)
                       : 1920u * 1080u;
            const bool measured_candidate =
               a830_memory_tier != 0 &&
               rp_state->drawcall_count >= min_draws &&
               mean_samples > 0 &&
               total_draw_call_bandwidth > 0 &&
               pass_pixel_count >= 320u * 180u &&
               pass_pixel_count <= max_pixels &&
               approx_tiles <= max_tiles &&
               pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;""",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            const bool dense_confirmed =
               q8428_policy && a830_memory_tier == 2 &&""",
    """            const bool dense_confirmed =
               q8428_policy && !is_a810 && a830_memory_tier == 2 &&""",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            const uint32_t tile_penalty =
               base_tile_penalty -
               (dense_confirmed ? MIN2(base_tile_penalty, 16u) : 0u);""",
    """            const uint32_t tile_penalty =
               is_a810
                  ? (approx_tiles > 2
                        ? (uint32_t) (approx_tiles - 2) *
                             (a810_profile == 2 ? 5u : 12u)
                        : 0u)
                  : base_tile_penalty -
                    (dense_confirmed ? MIN2(base_tile_penalty, 16u) : 0u);""",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """            const uint32_t entry_margin = 125 + tile_penalty +
               low_draw_penalty + (a830_memory_tier == 1 ? 50 : 0);""",
    """            /* A810 entry: 22% (safe) or 15.5% (experimental) base
             * estimated saving, plus physical tile and memory penalties.
             * A830 V15-L arithmetic is bit-for-bit unchanged.
             */
            const uint32_t entry_margin =
               (is_a810 ? (a810_profile == 2 ? 155u : 220u) : 125u) +
               tile_penalty + low_draw_penalty +
               (a830_memory_tier == 1 ? 50u : 0u);""",
)

edit(
    "src/freedreno/vulkan/tu_autotune.cc",
    """         smart, smart ? frane_a830_gmem_pressure_tier() : 2u);""",
    """         smart, smart ? frane_a830_gmem_pressure_tier() : 2u,
         frane_a810_gpu(device));""",
)

# V15-N's lean memory policy is A830 only; extend with independent A810
# options without changing the previously tested A830 behavior.
edit(
    "src/freedreno/vulkan/tu_device.cc",
    """   const uint64_t fraction = frane_a830 && frane_lean_budget ? 6 :
                             physical_device->info->chip >= A8XX ? 7 : 9;""",
    """   static const bool frane_a810_lean_budget = []() {
      const char *env = os_get_option("TU_A810_LEAN_BUDGET");
      return !env || strcmp(env, "0") != 0;
   }();
   const bool frane_a810 =
      id == 0x44010000ull || id == 0xffff44010000ull;
   const uint64_t fraction =
      (frane_a830 && frane_lean_budget) ||
      (frane_a810 && frane_a810_lean_budget) ? 6 :
      physical_device->info->chip >= A8XX ? 7 : 9;""",
)

edit(
    "src/freedreno/vulkan/tu_suballoc.cc",
    """   const bool drop_oversize_autotune =
      frane_lean_cache && frane_a830 &&
      strcmp(suballoc->name, "autotune_suballoc") == 0 &&""",
    """   static const bool frane_a810_lean_cache = []() {
      const char *env = os_get_option("TU_A810_LEAN_CACHE");
      return !env || strcmp(env, "0") != 0;
   }();
   const bool frane_a810 =
      id == 0x44010000ull || id == 0xffff44010000ull;
   const bool drop_oversize_autotune =
      ((frane_lean_cache && frane_a830) ||
       (frane_a810_lean_cache && frane_a810)) &&
      strcmp(suballoc->name, "autotune_suballoc") == 0 &&""",
)

print("V15-O: A810 KGSL alias + distinct 576-KiB GMEM profiles 0/1/2 + A810 lean budget/cache; preserve A830 V15-N")
