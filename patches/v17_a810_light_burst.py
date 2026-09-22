#!/usr/bin/env python3
"""A810 LIGHT/BURST experiment over the pinned upstream Mesa main V15Q.

Independent switches:
  TU_A810_SAFE_DEPTH_UBWC=0   -> previous V15Q depth image layout
  TU_A810_GMEM_BURST=0        -> previous V15Q GMEM selection frequency

GMEM isn't disabled, and image modifiers for explicit external images stay intact.
The graphics driver cannot observe an actual controller button press.
"""
from pathlib import Path

def edit(path, before, after, name):
    p = Path("mesa") / path
    s = p.read_text()
    n = s.count(before)
    if n != 1:
        raise SystemExit(f"{name}: source drift, anchors={n}")
    p.write_text(s.replace(before, after, 1))
    print(f"PASS {name}", flush=True)

edit("src/freedreno/vulkan/tu_image.cc",
"""   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* Layout computation begins here */""",
"""   /* A810 lighting diagnostic: preserve color UBWC and GMEM. For
    * internally allocated depth/stencil images only, try the ordinary
    * uncompressed depth image. NEVER contradict an explicit external
    * modifier: Android gralloc/AHB may own that resource's layout.
    * Depth-UBWC is only a suspected cause of sysmem-persistent flicker.
    */
   static const bool frane_safe_depth = []() {
      const char *env = os_get_option("TU_A810_SAFE_DEPTH_UBWC");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t frane_chip = device->physical_device->dev_id.chip_id;
   const bool frane_a810 =
      frane_chip == 0x44010000ull || frane_chip == 0xffff44010000ull;
   if (frane_a810 && frane_safe_depth &&
       modifier == DRM_FORMAT_MOD_INVALID &&
       vk_format_is_depth_or_stencil(image->vk.format))
      ubwc_enabled = false;

   if (TU_DEBUG(NOUBWC)) {
      ubwc_enabled = false;
   }

   /* Layout computation begins here */""", "A810 internal-depth lighting experiment")

edit("src/freedreno/vulkan/tu_autotune.cc",
"""            if (use_stats)
               a830_gmem_confidence.store(new_confidence,
                                          std::memory_order_relaxed);
            select_sysmem = new_confidence < 2;

            if (frane_a830_gmem_diag_enabled()) {""",
"""            if (use_stats)
               a830_gmem_confidence.store(new_confidence,
                                          std::memory_order_relaxed);
            select_sysmem = new_confidence < 2;

            /* A810 demand proxy: draw-dense passes after observed
             * profitability may claim ONE process-wide GMEM slot every
             * 100 ms. A Vulkan driver cannot inspect gamepad inputs.
             * Do not switch during an RP, override Mesa's attachment
             * requirements, force GMEM on an unprofitable pass, falsify
             * kernel GMEM geometry, or prematurely free submitted BOs.
             */
            if (is_a810) {
               static const bool a810_burst = []() {
                  const char *env = os_get_option("TU_A810_GMEM_BURST");
                  return !env || strcmp(env, "0") != 0;
               }();
               if (a810_burst && !select_sysmem) {
                  static std::atomic<uint64_t> next_slot_ns { 0 };
                  const uint64_t now = os_time_get_nano();
                  uint64_t previous =
                     next_slot_ns.load(std::memory_order_relaxed);
                  const bool active_draws = rp_state->drawcall_count >= 16;
                  const bool claimed = active_draws && now >= previous &&
                     next_slot_ns.compare_exchange_strong(
                        previous, now + 100'000'000ull,
                        std::memory_order_relaxed,
                        std::memory_order_relaxed);
                  select_sysmem = !claimed;
               }
            }

            if (frane_a830_gmem_diag_enabled()) {""", "A810 measured render-pass GMEM burst")

edit("src/freedreno/vulkan/tu_device.cc",
    '"Frane V15Q A810 UPSTREAM / Mesa " PACKAGE_VERSION MESA_GIT_SHA1);',
    '"Frane V17 A810 LIGHT-BURST / Mesa " PACKAGE_VERSION MESA_GIT_SHA1);',
    "V17 driver identity")
print("V17 A810 image and burst changes applied, A830 unchanged", flush=True)
