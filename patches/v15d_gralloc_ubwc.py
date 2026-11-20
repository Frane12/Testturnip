#!/usr/bin/env python3
"""V15-D: isolate whitebelyash's early A830 gralloc UBWC picture fix.

Sources:
  whitebelyash/mesa-tu8 commit 958a51540beb64ecd9ac78028692ce113a2d1b3b
  DiskDVD/A8XX-Y commit 6ccfee74478e63f2993e63697d8b730dd547b03e

Stock Mesa 26.1.4 UBWC stays ON. This changes *only* the gralloc fallback
modifier-detection gate, allowing modern gralloc without old 'gmsm' marker.
Unlike the original experimental hack, preserve numInts >= 2 bounds check.
No IMAGE-SAFE, no pipeline-library changes, no forced NOUBWC.
"""
from pathlib import Path

path = Path("mesa/src/util/u_gralloc/u_gralloc_fallback.c")
source = path.read_text()
before = """   uint32_t gmsm = ('g' << 24) | ('m' << 16) | ('s' << 8) | 'm';
   if (hnd->handle->numInts >= 2 && hnd->handle->data[hnd->handle->numFds] == gmsm) {"""
after = """   /* V15-D: Qualcomm newer gralloc can omit legacy 'gmsm' marker.
    * Still check there are at least two integer slots before reading flag.
    */
   if (hnd->handle->numInts >= 2) {"""
n = source.count(before)
if n != 1:
    raise SystemExit(f"Expected exactly one upstream gralloc marker gate, got {n}; no patch applied")
path.write_text(source.replace(before, after, 1))
print("V15-D: gralloc UBWC flag detection enabled without legacy gmsm; regular Vulkan UBWC ON")
