#!/usr/bin/env python3
from pathlib import Path

V = Path("mesa/src/freedreno/vulkan")
smart = (V / "frane_mesa_26318_a810_smart_gmem.h").read_text()
auto = (V / "tu_autotune.cc").read_text()
adaptive = (V / "frane_a830_v2_adaptive_gmem.h").read_text()
device = (V / "tu_device.cc").read_text()
helper = (V / "frane_a830_s2_bw2.h").read_text()

checks = {
    "helper cost model": "frane_a830_s2bw2_evaluate" in helper,
    "smart input gate": "bool a830_bw2 = false" in smart,
    "smart history fields": "a830_history_score" in smart and "a830_measured_armed" in smart,
    "runtime option": 'TU_FRANE_A830_BW2", true' in auto,
    "history snapshot": "frane_a830_v2_unpack_tail" in auto and "frane_2634_unpack_gmem_state" in auto,
    "fast rollback": "bw2.rollback_sysmem" in adaptive and "gmem_audit" in adaptive,
    "driver identity": "Turnip-Drnas A830 S2-BW2 Adaptive Tile Cost / Mesa " in device,
}
for name, ok in checks.items():
    if not ok:
        raise SystemExit(f"BW2 source check failed: {name}")
    print(f"BW2 PASS {name}")

print("A830 S2-BW2 source integration PASS")
