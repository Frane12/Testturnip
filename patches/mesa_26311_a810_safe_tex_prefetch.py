#!/usr/bin/env python3
"""Frane Mesa 26.3.11 A810 SAFE-TEX-PREFETCH EXP.

Layered strictly on 26.3.10 UBO-LOCALITY.

This does NOT flip A810's public has_fs_tex_prefetch device property.
Instead it adds a separate A810-only experimental path through Mesa's
existing texture-prefetch legality pass, with two extra hard restrictions:

  * at most ONE pre-dispatch texture fetch per fragment shader;
  * bindless texture/sampler fetches are excluded.

All existing Mesa restrictions remain in force: only simple 2D tex samples
from eligible interpolated coordinates, no array/sparse, no lod/bias/projector,
no offsets, no ddx/ddy, no MS sample index, and encodable fixed tex/sampler IDs.

A/B:
  TU_A810_26311_SAFE_TEX_PREFETCH=0  -> exact 26.3.10 behavior
  unset / 1                          -> one safe A810 prefetch maximum

Other GPUs preserve upstream behavior exactly.
"""
from pathlib import Path

ROOT = Path("mesa")


def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(
            f"26.3.11 SAFE-TEX-PREFETCH source drift: {label}: "
            f"expected 1 anchor, saw {n}: {old[:180]!r}"
        )
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.11 SAFE-TEX-PREFETCH PASS {label}", flush=True)


edit(
    "src/freedreno/ir3/ir3_compiler.h",
    """   uint16_t frane_26310_ubo_gap;

   /* The maximum number of constants, in vec4's, across the entire graphics
    * pipeline.
    */""",
    """   uint16_t frane_26310_ubo_gap;

   /* 26.3.11: A810-only experimental pre-dispatch texture fetch path.
    * The public device property remains false; this is a separate guarded
    * path so disabling it restores exact 26.3.10 behavior.
    */
   bool frane_26311_safe_tex_prefetch;

   /* The maximum number of constants, in vec4's, across the entire graphics
    * pipeline.
    */""",
    "add compiler-side A810 safe texture-prefetch policy",
)

edit(
    "src/freedreno/ir3/ir3_compiler.c",
    """      compiler->frane_26310_ubo_gap = gap;
   }

   /* TODO see if older GPU's were different here */""",
    """      compiler->frane_26310_ubo_gap = gap;
      compiler->frane_26311_safe_tex_prefetch =
         debug_get_bool_option("TU_A810_26311_SAFE_TEX_PREFETCH", true);
   }

   /* TODO see if older GPU's were different here */""",
    "enable A810 experimental path with same-binary opt-out",
)

edit(
    "src/freedreno/ir3/ir3_nir.h",
    """bool ir3_nir_lower_tex_prefetch(nir_shader *shader,
                                enum ir3_bary *prefetch_bary_type);""",
    """bool ir3_nir_lower_tex_prefetch(nir_shader *shader,
                                enum ir3_bary *prefetch_bary_type,
                                uint32_t max_prefetches,
                                bool allow_bindless);""",
    "extend prefetch pass with explicit safety policy",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """static bool
ok_tex_samp(nir_tex_instr *tex)
{
   if (has_src(tex, nir_tex_src_texture_handle)) {
      /* bindless case: */

      assert(has_src(tex, nir_tex_src_sampler_handle));

      return ok_bindless_src(tex, nir_tex_src_texture_handle) &&
             ok_bindless_src(tex, nir_tex_src_sampler_handle);""",
    """static bool
ok_tex_samp(nir_tex_instr *tex, bool allow_bindless)
{
   if (has_src(tex, nir_tex_src_texture_handle)) {
      /* bindless case: */
      if (!allow_bindless)
         return false;

      assert(has_src(tex, nir_tex_src_sampler_handle));

      return ok_bindless_src(tex, nir_tex_src_texture_handle) &&
             ok_bindless_src(tex, nir_tex_src_sampler_handle);""",
    "exclude bindless from guarded A810 path",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """static bool
lower_tex_prefetch_block(nir_block *block, ir3_prefetch_state *state)
{""",
    """static bool
lower_tex_prefetch_block(nir_block *block, ir3_prefetch_state *state,
                         bool allow_bindless)
{""",
    "thread bindless policy into block scan",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """      if (!ok_tex_samp(tex))
         continue;""",
    """      if (!ok_tex_samp(tex, allow_bindless))
         continue;""",
    "apply guarded texture/sampler policy",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """static bool
lower_tex_prefetch_func(nir_function_impl *impl, ir3_prefetch_state *state)
{""",
    """static bool
lower_tex_prefetch_func(nir_function_impl *impl, ir3_prefetch_state *state,
                        bool allow_bindless)
{""",
    "thread bindless policy into entrypoint scan",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """   bool progress = lower_tex_prefetch_block(block, state);""",
    """   bool progress = lower_tex_prefetch_block(block, state, allow_bindless);""",
    "pass bindless policy to first executable block",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,
                           enum ir3_bary *prefetch_bary_type)
{""",
    """bool
ir3_nir_lower_tex_prefetch(nir_shader *shader,
                           enum ir3_bary *prefetch_bary_type,
                           uint32_t max_prefetches,
                           bool allow_bindless)
{""",
    "add maximum-count and bindless policy arguments",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """      progress |= lower_tex_prefetch_func(function->impl, &state);""",
    """      progress |= lower_tex_prefetch_func(function->impl, &state,
                                               allow_bindless);""",
    "scan candidates under explicit policy",
)

edit(
    "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c",
    """      tex_prefetch_candidate *candidate;
      u_vector_foreach(candidate, &state.candidates) {
         if (candidate->bary == chosen_bary) {
            candidate->tex->op = nir_texop_tex_prefetch;
         }
      }

      *prefetch_bary_type = chosen_bary;
   } else {""",
    """      uint32_t converted = 0;
      tex_prefetch_candidate *candidate;
      u_vector_foreach(candidate, &state.candidates) {
         if (candidate->bary == chosen_bary &&
             converted < max_prefetches) {
            candidate->tex->op = nir_texop_tex_prefetch;
            converted++;
         }
      }

      progress = converted > 0;
      *prefetch_bary_type = progress ? chosen_bary : IJ_COUNT;
   } else {""",
    "hard-cap converted pre-dispatch fetch count",
)

edit(
    "src/freedreno/ir3/ir3_context.c",
    """   /* Enable the texture pre-fetch feature only a4xx onwards.  But
    * only enable it on generations that have been tested:
    */
   if ((so->type == MESA_SHADER_FRAGMENT) && compiler->info->props.has_fs_tex_prefetch) {
      NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch, &so->prefetch_bary_type);
   }""",
    """   /* Enable the regular texture pre-fetch path only on devices where
    * Mesa has validated the public property.  26.3.11 adds a deliberately
    * narrower A810 experiment without changing that public property:
    * one non-bindless eligible 2D fetch maximum.
    */
   if (so->type == MESA_SHADER_FRAGMENT) {
      if (compiler->info->props.has_fs_tex_prefetch) {
         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, ~0u, true);
      } else if (compiler->frane_26311_safe_tex_prefetch) {
         NIR_PASS(_, ctx->s, ir3_nir_lower_tex_prefetch,
                  &so->prefetch_bary_type, 1u, false);
      }
   }""",
    "add isolated A810 one-fetch compile path",
)

edit(
    "src/freedreno/vulkan/tu_device.cc",
    "Frane Mesa 26.3.10 A810 UBO-LOCALITY EXP / Mesa ",
    "Frane Mesa 26.3.11 A810 SAFE-TEX-PREFETCH EXP / Mesa ",
    "experimental driver identity",
)

# Surgical guards.
compiler_c = (ROOT / "src/freedreno/ir3/ir3_compiler.c").read_text()
compiler_h = (ROOT / "src/freedreno/ir3/ir3_compiler.h").read_text()
context = (ROOT / "src/freedreno/ir3/ir3_context.c").read_text()
lower = (ROOT / "src/freedreno/ir3/ir3_nir_lower_tex_prefetch.c").read_text()
nir_h = (ROOT / "src/freedreno/ir3/ir3_nir.h").read_text()
devs = (ROOT / "src/freedreno/common/freedreno_devices.py").read_text()

assert 'TU_A810_26311_SAFE_TEX_PREFETCH' in compiler_c
assert 'bool frane_26311_safe_tex_prefetch;' in compiler_h
assert '&so->prefetch_bary_type, 1u, false' in context
assert '&so->prefetch_bary_type, ~0u, true' in context
assert 'converted < max_prefetches' in lower
assert 'if (!allow_bindless)' in lower
assert 'ok_tex_samp(tex, allow_bindless)' in lower
assert 'uint32_t max_prefetches' in nir_h
assert 'bool allow_bindless' in nir_h

# A810 public capability must remain disabled. The whole point is to avoid
# pretending the generation is generally validated.
a810 = devs[devs.index('GPUId(chip_id=0xffff44010000'): ]
a810 = a810[:a810.index('add_gpus([', 1) if 'add_gpus([' in a810[1:] else len(a810)]
assert 'has_fs_tex_prefetch = True' not in a810
assert 'has_fs_tex_prefetch = False' in devs

# Preserve 26.3.10/26.3.9/26.3.8 wins.
assert 'TU_A810_26310_UBO_GAP' in compiler_c
assert 'TU_A810_2639_GMEM_DIM_GATING' in (ROOT / "src/freedreno/vulkan/tu_cmd_buffer.cc").read_text()
assert 'FRANE_2638_HOT_RP_SLOTS = 64' in (ROOT / "src/freedreno/vulkan/tu_autotune.h").read_text()
assert 'TU_A810_GMEM_RUNTIME' in (ROOT / "src/freedreno/vulkan/tu_autotune.cc").read_text()
assert 'V28-CLEAN: no driver present-mode override' in (ROOT / "src/freedreno/vulkan/tu_wsi.cc").read_text()
assert 'Frane Mesa 26.3.11 A810 SAFE-TEX-PREFETCH EXP' in (ROOT / "src/freedreno/vulkan/tu_device.cc").read_text()

print("Frane Mesa 26.3.11 A810 SAFE-TEX-PREFETCH EXP applied", flush=True)
