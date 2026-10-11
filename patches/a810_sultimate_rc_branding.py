#!/usr/bin/env python3
"""S Ultimate v1.0 RC: A810-only device branding, no DXVK binary fork.
Only Vulkan-reported deviceName changes for a standard DXVK devinfo HUD,
and is reversible via TU_FRANE_ULTIMATE_HUD_BRAND=0.
Explicitly configured Mesa force_vk_devicename retains priority.
Keep default device UUID, Vk driver ID, vendor ID, PCI/device id unchanged.
"""
from pathlib import Path
V=Path("mesa/src/freedreno/vulkan")
dev=V/"tu_device.cc"

def edit(old,new,name):
    s=dev.read_text()
    count=s.count(old)
    if count != 1:
        raise SystemExit(f"S Ultimate RC SOURCE DRIFT {name}: {count}")
    dev.write_text(s.replace(old,new,1))
    print("S Ultimate RC PASS",name,flush=True)

edit(
'''   snprintf(p->driverInfo, VK_MAX_DRIVER_INFO_SIZE,
            "Drnas-Turnip A810 ATUltimate Dynamic V3 / Mesa " PACKAGE_VERSION MESA_GIT_SHA1);''',
'''   /* Report our release identity only for A810, not on another GPU. */
   const bool drnas_a810_id =
      pdevice->dev_id.chip_id == 0x44010000ull ||
      pdevice->dev_id.chip_id == 0xffff44010000ull;
   snprintf(p->driverInfo, VK_MAX_DRIVER_INFO_SIZE,
            drnas_a810_id ?
               "Drnas-Turnip A810 S Ultimate v1.0 / Mesa " PACKAGE_VERSION MESA_GIT_SHA1 :
               "Mesa " PACKAGE_VERSION MESA_GIT_SHA1);''',
"Vulkan driverInfo A810-only label")
edit(
'''   snprintf(props->deviceName, sizeof(props->deviceName), "%s",
            (strlen(pdevice->instance->drirc.debug.force_vk_devicename) > 0) ?
            pdevice->instance->drirc.debug.force_vk_devicename : pdevice->name);''',
'''   /* DXVK devinfo HUD typically uses VkPhysicalDeviceProperties.deviceName.
    * This is cosmetic only. Vulkan IDs and pipeline-cache UUID remain
    * unchanged, and the existing user DRI device-name override wins.
    * Disable branding if any application uses the GPU name for compatibility.
    */
   static const bool drnas_hud_brand =
      debug_get_bool_option("TU_FRANE_ULTIMATE_HUD_BRAND", true);
   const bool drnas_a810_hud =
      pdevice->dev_id.chip_id == 0x44010000ull ||
      pdevice->dev_id.chip_id == 0xffff44010000ull;
   const char *forced_name =
      pdevice->instance->drirc.debug.force_vk_devicename;
   const char *reported_name =
      strlen(forced_name) > 0 ? forced_name :
      (drnas_hud_brand && drnas_a810_hud) ?
         "Drnas-Turnip A810 S Ultimate v1.0" : pdevice->name;
   snprintf(props->deviceName, sizeof(props->deviceName), "%s",
            reported_name);''',
"Opt-out deviceName branding in DXVK devinfo with DRI priority")
s=dev.read_text()
assert "TU_FRANE_ULTIMATE_HUD_BRAND" in s
assert "Drnas-Turnip A810 S Ultimate v1.0 / Mesa " in s
assert "VkPhysicalDeviceProperties.deviceName" in s
assert "vkGetPhysicalDeviceProperties" not in s
print("S Ultimate RC: deviceName wrapper label, UUID/ID untouched, opt-out present")
