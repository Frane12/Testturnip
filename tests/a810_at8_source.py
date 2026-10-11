#!/usr/bin/env python3
"""Verify AT8 in the actual patched Mesa sources, not just standalone host code."""
from pathlib import Path
import sys
v=Path(sys.argv[1] if len(sys.argv)>1 else "mesa") / "src/freedreno/vulkan"
auto=(v/"tu_autotune.cc").read_text()
dev=(v/"tu_device.cc").read_text()
header=(v/"frane_a810_at8_early.h").read_text()
for token in ("frane_at8_early_winner(", "debug_get_bool_option(\"TU_FRANE_AT8\", true)",
              "return on && frane_a810_at7_enabled(d);",
              "at8 && context_eligible, &at8_applied",
              'at8_applied ? "AT8_EARLY_GPU_WINNER"',
              "frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)",
              "frane_a810_rfc1_decision("):
    assert token in auto, token
assert auto.index("frane_at8_early_winner(") < auto.index("frane_at7_utility_winner(")
assert auto.index("frane_a810_gmem_pass_safe(device, cmd_state, pass, framebuffer)") < auto.index("frane_a810_rfc1_decision(")
for token in ("paired != 2","s.at7_saving_4us < 150","s.at7_noise_q8 > 24",
              "s.volatility != 0","at4.force_measure","frane_at4_decide("):
    assert token in header,token
assert "AT8 Early GPU Winner / Mesa" in dev
assert "TU_FRANE_AT5" not in auto
print("AT8 active runtime path, strict opt-out gate, post-safety telemetry, and AT5 exclusion PASS")
