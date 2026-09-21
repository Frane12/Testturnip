#!/usr/bin/env python3
"""V15-I: bandwidth baseline with separately opt-in A830 GMEM cost bias.

Apply after V15-D and V15-G to pinned Mesa 26.1.4. DEV=0 restores V15-G
selection. BIAS=1 enables a guarded, uncalibrated 5% cost experiment; default
keeps Mesa's 10% cost. Explicit TU_AUTOTUNE_ALGO retains upstream behavior
unless the user also explicitly enables BIAS. No register/lifetime changes.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_autotune.cc")
s = p.read_text()

def replace_once(before: str, after: str) -> None:
    global s
    found = s.count(before)
    if found != 1:
        raise SystemExit(f"V15-I anchor mismatch ({found} occurrences): {before[:130]!r}")
    s = s.replace(before, after, 1)

replace_once(
    """/** Configuration **/""",
    """/* Frane V15-I: target A830 only, never other Adreno 8xx revisions.
 * TU_A830_GMEM_DEV=0 is the emergency switch back to unmodified V15-G
 * autotune decisions without changing the driver ZIP.
 */
static bool
frane_a830_gmem_dev_enabled(const struct tu_device *device)
{
   static const bool dev_enabled = []() {
      const char *env = os_get_option("TU_A830_GMEM_DEV");
      return !env || strcmp(env, "0") != 0;
   }();
   const uint64_t chip_id = device->physical_device->dev_id.chip_id;
   return dev_enabled &&
          (chip_id == 0x44050001ull ||
           chip_id == 0x44050000ull ||
           chip_id == 0xffff44050000ull);
}

/* Separate opt-in: do not silently change an explicitly selected upstream
 * bandwidth algorithm. Read once, as with Mesa autotune environment options.
 */
static bool
frane_a830_gmem_bias_enabled()
{
   static const bool enabled = []() {
      const char *env = os_get_option("TU_A830_GMEM_BIAS");
      return env && strcmp(env, "1") == 0;
   }();
   return enabled;
}

/** Configuration **/""",
)
replace_once(
    """      if (algo_str)
         algo_strv = algo_str;
      else if (device->instance->autotune_algo)
         algo_strv = device->instance->autotune_algo;

      if (!algo_strv.empty()) {""",
    """      if (algo_str)
         algo_strv = algo_str;
      else if (frane_a830_gmem_dev_enabled(device))
          /* DXVK/VKD3D may have prefer_sysmem driconf on stock Mesa.
           * On this experimental build, allow bandwidth autotuning on
           * A830; still honor explicit TU_AUTOTUNE_ALGO and the opt-out.
           */
         algo_strv = "bandwidth";
      else if (device->instance->autotune_algo)
         algo_strv = device->instance->autotune_algo;

      if (!algo_strv.empty()) {""",
)
replace_once(
    """                                   const struct tu_framebuffer *framebuffer,
                                   const struct tu_render_pass_state *rp_state)
      {
         uint32_t pass_pixel_count = 0;""",
    """                                   const struct tu_framebuffer *framebuffer,
                                   const struct tu_render_pass_state *rp_state,
                                   bool frane_a830_gmem_bias)
      {
         uint32_t pass_pixel_count = 0;""",
)
replace_once(
    """         gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;

         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;""",
    """         /* Samples passed are a coverage proxy, not a timing measurement.
          * Restrict this uncalibrated bias to single-sample, single-view
          * passes; MSAA can inflate sample counts without extra overdraw.
          */
         const bool a830_candidate =
            frane_a830_gmem_bias &&
            pass->subpass_count == 1 &&
            pass->subpasses[0].samples == VK_SAMPLE_COUNT_1_BIT &&
            !cmd_state->per_layer_render_area &&
            pass->num_views <= 1 && framebuffer->layers == 1 &&
            rp_state->drawcall_count >= 12 &&
            pass_pixel_count > 0 && pass_pixel_count <= 1920u * 1080u &&
            mean_samples >= uint64_t(pass_pixel_count) * 2 &&
            pass->gmem_bandwidth_per_pixel < pass->sysmem_bandwidth_per_pixel;

         if (a830_candidate)
            gmem_bandwidth = (gmem_bandwidth * 21 + total_draw_call_bandwidth * 2) / 20;
         else
            gmem_bandwidth = (gmem_bandwidth * 11 + total_draw_call_bandwidth) / 10;

         bool select_sysmem = sysmem_bandwidth <= gmem_bandwidth;""",
)
replace_once(
    """   if (config.is_enabled(algorithm::BANDWIDTH))
      return history.bandwidth.get_optimal_mode(history, cmd_state, pass, framebuffer, rp_state);""",
    """   if (config.is_enabled(algorithm::BANDWIDTH))
      return history.bandwidth.get_optimal_mode(
          history, cmd_state, pass, framebuffer, rp_state,
          frane_a830_gmem_dev_enabled(device) && frane_a830_gmem_bias_enabled());""",
)
# Widen before multiplication so large/layered render areas cannot wrap into
# the <=1080p eligibility window or corrupt the bandwidth model.
replace_once("uint32_t pass_pixel_count = 0;", "uint64_t pass_pixel_count = 0;")
replace_once("pass_pixel_count += extent.width * extent.height;",
             "pass_pixel_count += uint64_t(extent.width) * extent.height;")
replace_once("extent.width * extent.height * MAX2(cmd_state->pass->num_views, cmd_state->framebuffer->layers);",
             "uint64_t(extent.width) * extent.height * MAX2(cmd_state->pass->num_views, cmd_state->framebuffer->layers);")

# Stage both files before writing: reject unexpected source without a partial patch.
d = Path("mesa/src/freedreno/vulkan/tu_device.cc")
ds = d.read_text()
before = '\"Mesa \" PACKAGE_VERSION MESA_GIT_SHA1);'
after = '\"Mesa \" PACKAGE_VERSION MESA_GIT_SHA1 \" | Frane-V15I-A830-GMEM-DEV\");'
if ds.count(before) != 1:
    raise SystemExit("V15-I driverInfo anchor mismatch; no files changed")
ds = ds.replace(before, after, 1)
p.write_text(s)
d.write_text(ds)
print("V15-I: A830 bandwidth baseline; guarded bias opt-in; real Vulkan driverInfo label")
