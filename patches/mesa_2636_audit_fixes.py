#!/usr/bin/env python3
"""26.3.6: targeted audit fixes over 26.3.5, unchanged rendering policies."""
from pathlib import Path

V = Path("mesa/src/freedreno/vulkan")
p = V / "tu_pipeline.cc"
s = p.read_text()
old = """         return VK_PIPELINE_COMPILE_REQUIRED;
      }

      result = tu_compile_shaders("""
new = """         /* 26.3.6: lookup owns one reference per hit, including hits
          * after a miss. These have not been transferred to pipeline yet.
          * Do not route through compile failure cleanup: compilation has
          * not run, and its ownership is separate. */
         for (unsigned stage = 0; stage < ARRAY_SIZE(shaders); stage++) {
            if (shaders[stage]) {
               vk_pipeline_cache_object_unref(&builder->device->vk,
                                               &shaders[stage]->base);
               shaders[stage] = NULL;
            }
         }
         return VK_PIPELINE_COMPILE_REQUIRED;
      }

      result = tu_compile_shaders("""
assert s.count(old) == 1, "compile-required source drift"
s = s.replace(old, new, 1)
a = s.index("   if (frane_stage_nir_enabled) {")
b = s.index("   unsigned char pipeline_blake3[BLAKE3_KEY_LEN];", a)
keys = s[a:b]
s = s[:a] + s[b:]
anchor = "      result = tu_compile_shaders("
assert s.count(anchor) == 1
# Preserve exact keys, but only compute when compilation is actually needed.
keys = "".join("   " + line if line.strip() else line for line in keys.splitlines(True))
s = s.replace(anchor, "      /* 26.3.6: full compiled-cache hits need no intermediate keys. */\n" + keys + anchor, 1)
assert s.index("return VK_PIPELINE_COMPILE_REQUIRED;", s.index("frane_2635_stage_probe_state")) < s.index("   if (frane_stage_nir_enabled) {")
p.write_text(s)
p = V / "tu_shader.cc"
s = p.read_text()
for obsolete in ("      bool frane_nir_hit = false;\n", "         frane_nir_hit = nir[stage] != NULL;\n", "      (void) frane_nir_hit;\n"):
    assert s.count(obsolete) == 1
    s = s.replace(obsolete, "", 1)
p.write_text(s)
p = V / "tu_device.cc"
s = p.read_text()
old = "Frane Mesa 26.3.5 A810 SHADER-PIPELINE EXP / Mesa "
assert s.count(old) == 1
p.write_text(s.replace(old, "Frane Mesa 26.3.6 A810 AUDIT-FIXES / Mesa ", 1))
# The corrected timeout helper is copied by the existing 26.3.1 layer.
assert "remaining_ns % 1000000ull" in (V / "frane_mesa_2631_sync.h").read_text()
print("26.3.6 PASS: cache-hit refs released; lazy NIR keys; ceil timeouts; unused local removed")
