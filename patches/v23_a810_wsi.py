#!/usr/bin/env python3
"""Embed optional A810 Vulkan presentation-mode preference in Turnip WSI.

Applied after V18 and V22 lean-profiled on pinned Mesa 26.2.3.
This is NOT a separate Vulkan API layer and does not affect GPU rendering,
BO lifetimes, application sync or cache/barrier commands.
"""
from pathlib import Path
import shutil

p = Path("mesa/src/freedreno/vulkan/tu_wsi.cc")
s = p.read_text()

def replace_once(old, new):
    global s
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V23 WSI source drift ({n}): {old[:100]!r}")
    s = s.replace(old, new, 1)

replace_once('#include "tu_device.h"', '''#include "tu_device.h"
#include "frane_present_policy.h"
#include "util/os_misc.h"
#include <stdio.h>''')

replace_once('''   physical_device->wsi_device.supports_modifiers = true;''', '''   /* A810-only built-in WSI presentation experiment. No extra Vulkan
    * loader layer or Android library is installed. Respect an explicit
    * MESA_VK_WSI_PRESENT_MODE set by the user before our preference.
    * Mesa's wsi_swapchain_get_present_mode validates surface support and
    * falls back to the application's request when unavailable.
    */
   const uint64_t frane_chip = physical_device->dev_id.chip_id;
   const bool frane_a810 =
      frane_chip == 0x44010000ull || frane_chip == 0xffff44010000ull;
   if (frane_a810 && !os_get_option("MESA_VK_WSI_PRESENT_MODE")) {
      const enum frane_present_choice choice =
         frane_present_parse(os_get_option("TU_FRANE_PRESENT_MODE"));
      switch (choice) {
      case FRANE_PRESENT_MAILBOX:
         physical_device->wsi_device.override_present_mode =
            VK_PRESENT_MODE_MAILBOX_KHR;
         break;
      case FRANE_PRESENT_FIFO:
         physical_device->wsi_device.override_present_mode =
            VK_PRESENT_MODE_FIFO_KHR;
         break;
      case FRANE_PRESENT_RELAXED:
         physical_device->wsi_device.override_present_mode =
            VK_PRESENT_MODE_FIFO_RELAXED_KHR;
         break;
      case FRANE_PRESENT_IMMEDIATE:
         physical_device->wsi_device.override_present_mode =
            VK_PRESENT_MODE_IMMEDIATE_KHR;
         break;
      case FRANE_PRESENT_OFF:
      default:
         /* Keep the WSI override sentinel initialized by upstream Mesa. */
         break;
      }
      const char *log = os_get_option("TU_FRANE_PRESENT_LOG");
      if (log && strcmp(log, "1") == 0)
         fprintf(stderr, "Frane V23 A810 WSI: choice=%u (MAILBOX=1,"
                         " FIFO=2, RELAXED=3, IMMEDIATE=4, OFF=0);"
                         " unsupported modes fall back to client\\n",
                 (unsigned)choice);
   }

   physical_device->wsi_device.supports_modifiers = true;''')

p.write_text(s)
shutil.copyfile("patches/frane_present_policy.h",
                p.parent / "frane_present_policy.h")

p = Path("mesa/src/freedreno/vulkan/tu_device.cc")
s = p.read_text()
old = "Frane A810 V22-LEAN-PROFILED / Mesa "
assert s.count(old) == 1, "V22 driver identity mismatch"
p.write_text(s.replace(old, "Frane A810 V23-LEAN-WSI / Mesa ", 1))
print("V23: A810 embedded WSI MAILBOX preference with native fallback", flush=True)
