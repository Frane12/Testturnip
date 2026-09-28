#!/usr/bin/env python3
"""Short display-name overlay for validated A810 V35.

No rendering, memory, sync, compiler, GMEM, WSI, or autotune logic changes.
Only the user-visible Vulkan driver identity is shortened so front-ends such
as AdrenoTools/Winlator do not show the full experiment provenance string.
"""
from pathlib import Path

p = Path("mesa/src/freedreno/vulkan/tu_device.cc")
s = p.read_text()

old = "Frane Mesa 26.3.35 A810 V34-DEEP-AUDIT-CLEAN EXP / Mesa "
new = "Turnip A810 V35 / Mesa "

n = s.count(old)
if n != 1:
    raise SystemExit(f"short-name source drift: expected 1 identity, got {n}")

p.write_text(s.replace(old, new, 1))

assert "Turnip A810 V35 / Mesa " in p.read_text()
assert old not in p.read_text()
print("A810 V35 short display name applied", flush=True)
