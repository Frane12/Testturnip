#!/usr/bin/env python3
"""V14-A diagnostic: preserve V13 IMAGE-SAFE and add A8XX indirect-draw WFM.

This is NOT a general render-target clear patch. The change tests whether
indirect draw ordering contributes to Dunia FC3/FC4 stale rectangular shadows.
Based on the A8XX indirect draw WFM quirk from StevenMXZ's tu8_kgsl_26.patch.
"""
from pathlib import Path
import subprocess
import sys

subprocess.run([sys.executable, "patches/v13_a830.py", "a830-image-safe"], check=True)
path = Path("mesa/src/freedreno/vulkan/tu_cmd_buffer.cc")
src = path.read_text()
anchor = """   if (cmd->device->physical_device->info->props.indirect_draw_wfm_quirk)
      draw_wfm(cmd);"""
assert src.count(anchor) == 2, "Expected exactly two indirect draw WFM anchors"
replacement = """   /* V14-A: A8XX indirect-draw ordering diagnostic (both draw variants).
    * Preserve V13 image/UBWC behavior. Do not clear render targets.
    */
   if (cmd->device->physical_device->info->props.indirect_draw_wfm_quirk ||
       CHIP >= A8XX)
      draw_wfm(cmd);"""
path.write_text(src.replace(anchor, replacement))
print("V14-A A830 image-safe + A8XX indirect draw WFM applied")
