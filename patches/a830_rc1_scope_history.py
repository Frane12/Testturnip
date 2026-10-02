#!/usr/bin/env python3
"""Drnas Turnip A830 1.0 RC1 SCOPE-HISTORY.

Layered strictly on Drnas Turnip A830 V59 LRZ-CLEAN.

This patch deliberately leaves the proven A830 integration points untouched and
replaces only the V2 adaptive-GMEM policy header with the RC1 scope-history
state machine.

RC1 policy:
- throughput/distribution first; one pathological minimum does not steer policy;
- paired measured GMEM/SYSMEM history;
- true hysteresis (+/-3 arm, zero release, opposite threshold to switch);
- 25% tail-envelope weight instead of V2's 50%;
- no synthetic loser-mode probe;
- periodic audit means "fall through to existing SMART/PROFILED";
- keep A830 measured-GMEM boost and widen it slightly only after real timing and
  Mesa layout structure agree;
- no A810 fixed tile/depth thresholds, PWR_MAX or sampled-depth mechanisms.

No LRZ, barriers, GMEM addresses, attachment programming, shader scheduling,
WSI or synchronization changes are introduced here.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

src = Path("patches/frane_a830_rc1_scope_history.h")
dst = V / "frane_a830_v2_adaptive_gmem.h"
if not src.exists() or not dst.exists():
    raise SystemExit("A830 RC1 source drift: policy header path missing")

shutil.copyfile(src, dst)
print("A830 RC1 PASS replace V2 policy with scope-history state machine", flush=True)

dev = V / "tu_device.cc"
s = dev.read_text()
old = "Drnas Turnip A830 V59 / Mesa "
new = "Drnas Turnip A830 1.0 RC1 SCOPE-HISTORY / Mesa "
if s.count(old) != 1:
    raise SystemExit(
        f"A830 RC1 source drift: expected V59 identity once, found {s.count(old)}")
dev.write_text(s.replace(old, new, 1))
print("A830 RC1 PASS display identity", flush=True)

a = (V / "tu_autotune.cc").read_text()
h = dst.read_text()
lrz = (V / "tu_lrz.cc").read_text()
kg = (V / "tu_knl_kgsl.cc").read_text()
img = (V / "tu_image.cc").read_text()
q = (V / "tu_queue.cc").read_text()
d = dev.read_text()

# Integration is still the validated A830 V2/V59 path.
for needle in (
    "frane_a830_v2_flags",
    "frane_a830_v2_tail_word",
    "frane_a830_v2_update_tail",
    "frane_a830_v2_decide",
    'TU_FRANE_A830_BOOST", true',
    'TU_FRANE_A830_LEARN", true',
    "TU_A830_26320_PROFILED_GMEM",
    "TU_A830_26320_SMART_GMEM",
):
    assert needle in a, needle

# New policy invariants.
for needle in (
    "penalty / 4",
    "paired < 4",
    "score >= 3",
    "score <= -3",
    "state.hold",
    "history.hold",
    "sysmem_probability >= 80",
    "sysmem_probability <= 20",
    "confidence >= 6 ? 6 : 5",
    "layout.structure_score >= 80",
    "layout.structure_score >= 70",
    "layout.structure_score >= 64",
    "sysmem_probability <= 55",
    "out.force_measure = false",
):
    assert needle in h, needle

# The old probe policy is intentionally gone from the replacement header.
assert "loser_probe" not in h
assert "out.select_sysmem = (decision_word & mask) == 0" not in h

# Exact A830 target stays exact.
for chip in ("0x44050000", "0x44050001", "0xffff44050000"):
    assert chip in a, chip
    assert chip in lrz, chip

# Preserve A830 V59 LRZ translation and earlier hang fixes.
assert "frane_a830_v59_lrz_gpu" in lrz
assert "(frane_a830_v59 && !z_write_enable)" in lrz
assert "if (!frane_a830_v59 || z_write_enable)" in lrz
assert "FRANE_2631_POLL_READY" in kg
assert "frane_2631_deadline_ns" in kg
assert "pthread_mutex_unlock(&device->submit_mutex);" in q

# Risky A810-only mechanisms remain off A830.
assert "TU_A810_PWR_MAX" in kg
assert "TU_A830_PWR_MAX" not in kg
assert "TU_A810_SAMPLED_DEPTH_DIAG" in img
assert "TU_A830_SAMPLED_DEPTH_DIAG" not in img

assert "Drnas Turnip A830 1.0 RC1 SCOPE-HISTORY / Mesa " in d

print("Drnas Turnip A830 1.0 RC1 SCOPE-HISTORY applied and audited", flush=True)
