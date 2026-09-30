#!/usr/bin/env python3
"""Drnas Turnip V52 CLEAN-INTERFACE.

Organizational layer on top of V51. No render policy, allocator, shader,
barrier, LRZ, load/store, tiling or autotune decision is changed.

This patch only:
1. renames the public Frane A810 experiment environment variables to a short,
   stable TU_FRANE_* namespace;
2. updates the display identity to V52.

The goal is to make phone/tablet A/B testing practical without typing build
numbers into every variable name.
"""
from pathlib import Path

ROOT = Path("mesa")
SRC_ROOTS = (
    ROOT / "src/freedreno/vulkan",
    ROOT / "src/freedreno/ir3",
)

RENAMES = {
    "TU_A810_26320_GMEM_TURBO": "TU_FRANE_GMEM_TURBO",
    "TU_A810_26326_GMEM_SAFETY": "TU_FRANE_GMEM_SAFE",
    "TU_A810_26327_GMEM_SIMPLE_DEPTH": "TU_FRANE_SIMPLE_DEPTH",
    "TU_A810_26328_GMEM_SIMPLE_DS": "TU_FRANE_SIMPLE_DS",
    "TU_A810_26329_GMEM_STENCIL_LOADSTORE": "TU_FRANE_STENCIL_LS",
    "TU_A810_26330_GMEM_PACKED_DS": "TU_FRANE_PACKED_DS",
    "TU_A810_26337_GMEM_MASK_PACK": "TU_FRANE_GMEM_MASK",
    "TU_A810_26339_GMEM_PRESSURE_BOUND": "TU_FRANE_GMEM_PRESSURE",
    "TU_A810_26346_CB_PRESSURE_SCORE": "TU_FRANE_CB_SCORE",
    "TU_A810_26347_CB_PROFILE_MODE": "TU_FRANE_CB_MODE",
    "TU_A810_26347_CB_PROFILE_LOG": "TU_FRANE_CB_LOG",
    "TU_A810_26348_GMEM_STICKY_MODE": "TU_FRANE_STICKY",
    "TU_A810_26349_GMEM_FRONTIER_MODE": "TU_FRANE_GMEM_MODE",
    "TU_A810_26350_DEPTH_FRONTIER_MODE": "TU_FRANE_DEPTH_MODE",
    "TU_A810_26351_DEPTH_MIN_DRAWS": "TU_FRANE_DEPTH_DRAWS",
}

changed = {}
for root in SRC_ROOTS:
    if not root.exists():
        continue
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".c", ".cc", ".cpp", ".h", ".hpp"}:
            continue
        text = path.read_text()
        original = text
        local = []
        for old, new in RENAMES.items():
            n = text.count(old)
            if n:
                text = text.replace(old, new)
                local.append((old, new, n))
        if text != original:
            path.write_text(text)
            changed[str(path)] = local

device = ROOT / "src/freedreno/vulkan/tu_device.cc"
s = device.read_text()
old_id = "Drnas Turnip V51 / Mesa "
if s.count(old_id) != 1:
    raise SystemExit(f"V52 identity drift: expected one {old_id!r}, found {s.count(old_id)}")
device.write_text(s.replace(old_id, "Drnas Turnip V52 / Mesa ", 1))

# The current V51 test controls must all have been renamed.
required = {
    "TU_FRANE_CB_SCORE",
    "TU_FRANE_GMEM_MODE",
    "TU_FRANE_DEPTH_MODE",
    "TU_FRANE_DEPTH_DRAWS",
}
joined = "\n".join(
    p.read_text()
    for root in SRC_ROOTS if root.exists()
    for p in root.rglob("*")
    if p.is_file() and p.suffix in {".c", ".cc", ".cpp", ".h", ".hpp"}
)
for name in required:
    assert name in joined, name

for old in RENAMES:
    assert old not in joined, old

assert "Drnas Turnip V52 / Mesa " in device.read_text()

print("Drnas Turnip V52 CLEAN-INTERFACE applied", flush=True)
for path, items in sorted(changed.items()):
    for old, new, n in items:
        print(f"  {path}: {old} -> {new} ({n})", flush=True)
