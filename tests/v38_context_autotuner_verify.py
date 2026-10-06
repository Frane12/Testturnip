#!/usr/bin/env python3
from pathlib import Path

root = Path("mesa/src/freedreno/vulkan")
src = (root / "tu_autotune.cc").read_text()
dev = (root / "tu_device.cc").read_text()
hdr = (root / "frane_v38_context_autotune.h").read_text()
gmem = (root / "tu_pass.cc").read_text()

checks = (
    'TU_A810_V38_CONTEXT_AUTOTUNER", true',
    "frane_v38_context_word(context)",
    "observe_context_reversal",
    "reversal_votes",
    "at.frane_save_profile(hash, 50)",
    "XXH3_64bits_withSeed",
)
for needle in checks:
    assert needle in src, needle

assert "frane_v38_context_input" in hdr
assert "frane_v38_reversal_vote" in hdr
assert "Turnip A810 V38 AUTOTUNER / Mesa " in dev

# Explicitly prove the allocator experiment stayed present.
assert 'TU_A810_26338_GMEM_SEARCH", true' in gmem
assert "frane_refine_gmem_mask_candidate" in gmem
assert "upper <= ctx->best_pixels" in gmem

print("V38 CONTEXT AUTOTUNER verification PASS")
