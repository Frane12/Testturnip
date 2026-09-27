#!/usr/bin/env python3
"""Frane Mesa 26.3.12 A810 DUAL-TEX-PREFETCH EXP.

Layered strictly on 26.3.11 SAFE-TEX-PREFETCH.

26.3.11 proved useful on-device with a one-fetch cap. This experiment keeps
all of its legality rules and only raises the A810 cap from one to TWO
pre-dispatch fragment texture fetches.

A/B ladder in the same binary:
  default                                  -> up to 2 safe fetches
  TU_A810_26312_DUAL_TEX_PREFETCH=0       -> 26.3.11 one-fetch behavior
  TU_A810_26311_SAFE_TEX_PREFETCH=0       -> prefetch path fully disabled

Bindless remains rejected and A810's public has_fs_tex_prefetch capability
remains false. Other GPUs preserve upstream behavior.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.12 DUAL-TEX-PREFETCH source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.12 DUAL-TEX-PREFETCH PASS {label}", flush=True)


edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26311_safe_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
    * pipeline.
    */""",
    """   bool frane_26311_safe_tex_prefetch;

   /* 26.3.12: second-stage A810 experiment.  When enabled, the guarded
    * 26.3.11 path may convert two legal samples instead of one.
    */
   bool frane_26312_dual_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
    * pipeline.
    */""",
    "add compiler-side dual-prefetch switch",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26311_safe_tex_prefetch =
         debug_get_bool_option("TU_A810_26311_SAFE_TEX_PREFETCH", true);
   }

   /* TODO see if older GPU's were different here */""",
    """      compiler->frane_26311_safe_tex_prefetch =
         debug_get_bool_option("TU_A810_26311_SAFE_TEX_PREFETCH", true);
      compiler->frane_26312_dual_tex_prefetch =
         debug_get_bool_option("TU_A810_26312_DUAL_TEX_PREFETCH", true);
   }

   /* TODO see if older GPU's were different here */""",
    "enable same-binary 2-versus-1 A/B switch",
)

edit(
    "src/freedreno/ir3/ir3_context.c",
    """      } else if (compiler->frane_26311_safe_tex_prefetch) {
         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, 1u, false);
      }""",
    """      } else if (compiler->frane_26311_safe_tex_prefetch) {
         /* A810 remains on the restricted non-bindless path.  26.3.12
          * only increases the candidate budget from one to two, still well
          * below IR3_MAX_SAMPLER_PREFETCH (4).
          */
         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type,
                  compiler->frane_26312_dual_tex_prefetch ? 2u : 1u, false);
      }""",
    "raise guarded A810 cap to two with one-fetch fallback",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.11 A810 SAFE-TEX-PREFETCH EXP / Mesa ",
    "Frane Mesa 26.3.12 A810 DUAL-TEX-PREFETCH EXP / Mesa ",
    "experimental driver identity",
)

# Surgical guards.
compiler_c = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
compiler_h = (ROOT / "src/freedreno/ir3/ir3_compiler.h").read_text()
context = (ROOT / "src/freedreno/ir3/ir3_context.c").read_text()
lower = (ROOT / "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c").read_text()
devs = (ROOT / "src/freedreno/common/freedreno_devices.py").read_text()

assert 'TU_A810_26311_SAFE_TEX_PREFETCH' in compiler_c
assert 'TU_A810_26312_DUAL_TEX_PREFETCH' in compiler_c
assert 'bool frane_26312_dual_tex_prefetch;' in compiler_h
assert 'compiler->frane_26312_dual_tex_prefetch ? 2u : 1u' in context
assert '&so->prefetch_bary_type, ~0u, true' in context
assert 'converted < max_prefetches' in lower
assert 'if (!allow_bindless)' in lower

# Keep the public device capability disabled.  This is still an experiment,
# not a claim that generic A810 prefetch support has been validated.
a810_pos = devs.index('GPUId(chip_id=0xffff44010000, name="Adreno (TM) 810")')
assert 'has_fs_tex_prefetch = True' not in devs[max(0, a810_pos - 2500):a810_pos + 1800]

# Preserve the previous experimental stack.
assert 'TU_A810_26310_UBO_GAP' in compiler_c
assert 'TU_A810_2639_GMEM_DIM_GATING' in (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
assert 'FRANE_2638_HOT_RP_SLOTS = 64' in (ROOT / "src/freedreno/vulkan/tu_autotune.h").read_text()
assert 'TU_A810_GMEM_RUNTIME' in (ROOT / "src/freedreno/vulkan/tu_autotune.cc").read_text()
assert 'V28-CLEAN: no driver present-mode override' in (ROOT / "src/freedreno/vulkan/tu_wsi.cc").read_text()
assert 'Frane Mesa 26.3.12 A810 DUAL-TEX-PREFETCH EXP' in (ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

print("Frane Mesa 26.3.12 A810 DUAL-TEX-PREFETCH EXP applied", flush=True)
