#!/usr/bin/env python3
"""Frane Mesa 26.3.14 A810 LRZ-SAFE + TRIPLE-PREFETCH EXP.

Layered strictly on 26.3.13 LRZ-FASTPATH.

Correctness fix:
  - remove the 26.3.13 fragment-shader-signature LRZ dirty suppression;
  - restore upstream tu_bind_fs() behavior: every real FS change marks both
    TU_CMD_DIRTY_LRZ and TU_CMD_DIRTY_FS;
  - keep the conservative sparse/undefined color-attachment LRZ
    classification from 26.3.13.

Small optional A810 experiment:
  TU_A810_26314_TRIPLE_TEX_PREFETCH=0 (default)
      -> keep the proven 26.3.12 two-fetch cap.
  TU_A810_26314_TRIPLE_TEX_PREFETCH=1
      -> allow up to THREE legal non-bindless fragment texture prefetches.

The third prefetch stays behind the same 26.3.11 legality filters and below
IR3_MAX_SAMPLER_PREFETCH (4).  It is intentionally default-off so LRZ
correctness can be validated independently first.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.14 LRZ-SAFE source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.14 LRZ-SAFE PASS {label}", flush=True)


# ---------------------------------------------------------------------------
# 1) Correctness: completely remove the 26.3.13 FS-signature LRZ skip.
#    The sparse color-attachment optimization in tu_pipeline.cc is retained.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """#include "vk_render_pass.h"
#include "vk_util.h"
#include "util/u_debug.h"
""",
    """#include "vk_render_pass.h"
#include "vk_util.h"
""",
    "remove now-unused LRZ experiment debug include",
)

edit(
    "src/freedreno/vulkan/tu_cmd_buffer.cc",
    """static bool
frane_26313_a810_lrz_fastpath(const struct tu_cmd_buffer *cmd)
{
   static const bool enabled =
      debug_get_bool_option("TU_A810_26313_LRZ_FASTPATH", true);

   if (!enabled || !cmd || !cmd->device || !cmd->device->physical_device)
      return false;

   const uint64_t chip = cmd->device->physical_device->dev_id.chip_id;
   return chip == 0x44010000ull || chip == 0xffff44010000ull;
}

static bool
frane_26313_same_lrz_fs_signature(const struct tu_shader *a,
                                  const struct tu_shader *b)
{
   if (!a || !b || !a->variant || !b->variant)
      return false;

   const struct ir3_shader_variant *av = a->variant;
   const struct ir3_shader_variant *bv = b->variant;

   /* Keep this list synchronized with every FS field consumed by
    * tu6_calculate_lrz_state() and tu6_build_depth_plane_z_mode().
    */
   return av->writes_pos == bv->writes_pos &&
          av->fs.early_fragment_tests == bv->fs.early_fragment_tests &&
          av->fs.depth_layout == bv->fs.depth_layout &&
          av->has_kill == bv->has_kill &&
          av->writes_smask == bv->writes_smask &&
          a->fs.lrz.status == b->fs.lrz.status &&
          a->fs.lrz.force_late_z == b->fs.lrz.force_late_z &&
          a->fs.sample_shading == b->fs.sample_shading &&
          a->fs.dynamic_input_attachments_used ==
             b->fs.dynamic_input_attachments_used;
}

static void
tu_bind_fs(struct tu_cmd_buffer *cmd, struct tu_shader *fs)
{
   struct tu_shader *old_fs = cmd->state.shaders[MESA_SHADER_FRAGMENT];

   if (old_fs != fs) {
      const bool same_lrz_signature =
         frane_26313_a810_lrz_fastpath(cmd) &&
         frane_26313_same_lrz_fs_signature(old_fs, fs);

      cmd->state.shaders[MESA_SHADER_FRAGMENT] = fs;
      cmd->state.dirty |= TU_CMD_DIRTY_FS;

      if (!same_lrz_signature)
         cmd->state.dirty |= TU_CMD_DIRTY_LRZ;
   }
}
""",
    """static void
tu_bind_fs(struct tu_cmd_buffer *cmd, struct tu_shader *fs)
{
   if (cmd->state.shaders[MESA_SHADER_FRAGMENT] != fs) {
      cmd->state.shaders[MESA_SHADER_FRAGMENT] = fs;
      cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;
   }
}
""",
    "restore upstream LRZ dirtying on every fragment-shader change",
)

# ---------------------------------------------------------------------------
# 2) Small independent experiment: optional third *legal* A810 prefetch.
#    Default remains the already-tested dual-prefetch behavior.
# ---------------------------------------------------------------------------
edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   bool frane_26312_dual_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    """   bool frane_26312_dual_tex_prefetch;

   /* 26.3.14: optional third guarded A810 fragment texture prefetch.
    * Default-off so the LRZ correctness fix can be tested independently.
    */
   bool frane_26314_triple_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
""",
    "add compiler-side triple-prefetch experiment switch",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26312_dual_tex_prefetch =
         debug_get_bool_option("TU_A810_26312_DUAL_TEX_PREFETCH", true);
   }
""",
    """      compiler->frane_26312_dual_tex_prefetch =
         debug_get_bool_option("TU_A810_26312_DUAL_TEX_PREFETCH", true);
      compiler->frane_26314_triple_tex_prefetch =
         debug_get_bool_option("TU_A810_26314_TRIPLE_TEX_PREFETCH", false);
   }
""",
    "add default-off A810 triple-prefetch A/B switch",
)

edit(
    "src/freedreno/ir3/ir3_context.c",
    """                  &so->prefetch_bary_type,
                  compiler->frane_26312_dual_tex_prefetch ? 2u : 1u, false);
""",
    """                  &so->prefetch_bary_type,
                  compiler->frane_26314_triple_tex_prefetch ? 3u :
                  (compiler->frane_26312_dual_tex_prefetch ? 2u : 1u), false);
""",
    "raise guarded prefetch cap from two to three only when explicitly enabled",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.13 A810 LRZ-FASTPATH EXP / Mesa ",
    "Frane Mesa 26.3.14 A810 LRZ-SAFE TRIPLE-PREFETCH EXP / Mesa ",
    "experimental driver identity",
)

# Surgical guards.
cmd = (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
pipeline = (ROOT / "src/freedreno/vulkan/tu_pipeline.cc").read_text()
compiler_c = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
compiler_h = (ROOT / "src/freedreno/ir3/ir3_compiler.h").read_text()
context = (ROOT / "src/freedreno/ir3/ir3_context.c").read_text()
lower = (ROOT / "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c").read_text()
devs = (ROOT / "src/freedreno/common/freedreno_devices.py").read_text()
dev = (ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

# 26.3.13 sparse-color LRZ classification is intentionally preserved.
assert 'TU_A810_26313_LRZ_FASTPATH' in pipeline
assert 'frane_lrz ? total_color_attachments : cb->attachment_count' in pipeline
assert 'const bool logic_reads_dest' in pipeline

# The unsafe FS-signature suppression must be completely gone.
assert 'frane_26313_same_lrz_fs_signature' not in cmd
assert 'frane_26313_a810_lrz_fastpath' not in cmd
assert 'same_lrz_signature' not in cmd
assert 'cmd->state.dirty |= TU_CMD_DIRTY_LRZ | TU_CMD_DIRTY_FS;' in cmd

# Optional triple-prefetch remains inside the existing safe/non-bindless path.
assert 'TU_A810_26311_SAFE_TEX_PREFETCH' in compiler_c
assert 'TU_A810_26312_DUAL_TEX_PREFETCH' in compiler_c
assert 'TU_A810_26314_TRIPLE_TEX_PREFETCH' in compiler_c
assert 'bool frane_26314_triple_tex_prefetch;' in compiler_h
assert 'compiler->frane_26314_triple_tex_prefetch ? 3u :' in context
assert 'compiler->frane_26312_dual_tex_prefetch ? 2u : 1u' in context
assert 'converted < max_prefetches' in lower
assert 'if (!allow_bindless)' in lower

# Keep the public capability disabled: this is still a guarded experiment.
a810_pos = devs.index('GPUId(chip_id=0xffff44010000, name="Adreno (TM) 810")')
assert 'has_fs_tex_prefetch = True' not in devs[max(0, a810_pos - 2500):a810_pos + 1800]

# Preserve the rest of the optimization stack.
assert 'TU_A810_26310_UBO_GAP' in compiler_c
assert 'TU_A810_2639_GMEM_DIM_GATING' in cmd
assert 'TU_A810_GMEM_RUNTIME' in (
    ROOT / "src/freedreno/vulkan/tu_autotune.cc").read_text()
assert 'V28-CLEAN: no driver present-mode override' in (
    ROOT / "src/freedreno/vulkan/tu_wsi.cc").read_text()
assert 'Frane Mesa 26.3.14 A810 LRZ-SAFE TRIPLE-PREFETCH EXP' in dev

print("Frane Mesa 26.3.14 A810 LRZ-SAFE TRIPLE-PREFETCH EXP applied", flush=True)
