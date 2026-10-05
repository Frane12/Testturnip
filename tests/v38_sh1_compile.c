#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "compiler/nir/nir_builder.h"
#include "ir3.h"
#include "ir3_compiler.h"
#include "ir3_nir.h"
#include "ir3_shader.h"

static nir_shader *make_shader(struct ir3_compiler *c, bool fragment,
                               unsigned width, unsigned seed)
{
   nir_builder b = nir_builder_init_simple_shader(
      fragment ? MESA_SHADER_FRAGMENT : MESA_SHADER_COMPUTE,
      ir3_get_compiler_options(c), "sh1-%u-%u-%u", fragment, width, seed);
   nir_def *values[64];
   if (fragment) {
      nir_def *coord = nir_load_frag_coord(&b);
      for (unsigned i = 0; i < width; i++) {
         nir_tex_instr *tex = nir_tex_instr_create(b.shader, 1);
         tex->op = nir_texop_tex;
         tex->sampler_dim = GLSL_SAMPLER_DIM_2D;
         tex->dest_type = nir_type_float32;
         tex->coord_components = 2;
         tex->texture_index = tex->sampler_index = i % 4;
         tex->src[0].src_type = nir_tex_src_coord;
         tex->src[0].src = nir_src_for_ssa(nir_fmul_imm(
            &b, nir_channels(&b, coord, 3), 0.001f * (i + seed + 1)));
         nir_def_init(&tex->instr, &tex->def, 4, 32);
         nir_builder_instr_insert(&b, &tex->instr);
         values[i] = nir_fmul_imm(&b, &tex->def, 0.25f + i * 0.01f);
      }
      b.shader->info.num_textures = b.shader->info.num_samplers = 4;
   } else {
      b.shader->info.workgroup_size[0] = 32;
      b.shader->info.workgroup_size[1] = b.shader->info.workgroup_size[2] = 1;
      b.shader->info.num_ssbos = 1;
      nir_def *offset = nir_imul_imm(&b,
         nir_channel(&b, nir_load_local_invocation_id(&b), 0), width * 4);
      for (unsigned i = 0; i < width; i++) {
         nir_def *load = nir_load_ssbo(&b, 1, 32, nir_imm_int(&b, 0),
            nir_iadd_imm(&b, offset, i * 4), .align_mul = 4);
         values[i] = nir_fmul_imm(&b, nir_u2f32(&b, load),
                                 0.01f * (i + seed + 1));
      }
   }
   nir_def *sum = values[0];
   for (unsigned i = 1; i < width; i++)
      sum = nir_fadd(&b, sum, nir_fsin(&b, values[i]));
   if (seed & 1) {
      nir_push_if(&b, nir_flt_imm(&b, nir_channel(&b, sum, 0), 0.5));
      nir_def *left = nir_fmul_imm(&b, sum, 0.9);
      nir_push_else(&b, NULL);
      nir_def *right = nir_fadd_imm(&b, sum, 0.1);
      nir_pop_if(&b, NULL);
      sum = nir_if_phi(&b, left, right);
   }
   if (fragment) {
      nir_variable *out = nir_variable_create(b.shader, nir_var_shader_out,
                                              glsl_vec4_type(), "out_color");
      out->data.location = FRAG_RESULT_DATA0;
      nir_store_var(&b, out, sum, 15);
   } else {
      nir_store_ssbo(&b, sum, nir_imm_int(&b, 0), nir_imm_int(&b, 0),
                     .write_mask = 1, .align_mul = 4);
   }
   nir_validate_shader(b.shader, "SH1 input");
   return b.shader;
}

int main(void)
{
   setenv("MESA_SHADER_CACHE_DISABLE", "true", 1);
   glsl_type_singleton_init_or_ref();
   const struct fd_dev_id id = {.chip_id = UINT64_C(0xffff44010000)};
   const struct ir3_compiler_options opts = {};
   struct ir3_compiler *c = ir3_compiler_create(NULL, &id, fd_dev_info_raw(&id), &opts);
   assert(c && c->frane_26317_adaptive_sched);
   struct ir3_shader_options options = {};
   struct ir3_shader_key key = {};
   unsigned changed = 0, cases = 0;
   unsigned modes[] = {0, 0, 1};
   for (unsigned fragment = 0; fragment < 2; fragment++) {
      for (unsigned width = 4; width <= (fragment ? 16u : 64u); width *= 2) {
         for (unsigned seed = 0; seed < 8; seed++) {
            void *reference = NULL;
            size_t reference_size = 0;
            for (unsigned run = 0; run < 3; run++) {
               c->frane_sh1_mode = modes[run];
               c->frane_sh1_threshold = 35;
               nir_shader *nir = make_shader(c, fragment, width, seed);
               ir3_finalize_nir(c, &options.nir_options, nir);
               nir_validate_shader(nir, "SH1 finalized");
               struct ir3_shader *s = ir3_shader_from_nir(c, nir, &options);
               struct ir3_shader_variant *v = ir3_shader_create_variant(s, &key, true);
               assert(v && v->bin && v->info.size > 0);
               if (run == 0) {
                  reference_size = v->info.size;
                  reference = malloc(reference_size);
                  assert(reference);
                  memcpy(reference, v->bin, reference_size);
               } else {
                  bool different = reference_size != v->info.size ||
                     memcmp(reference, v->bin, reference_size) != 0;
                  if (run == 1)
                     assert(!different);
                  else
                     changed += different;
               }
               printf("stage=%u width=%u seed=%u mode=%u instr=%u nop=%u reg=%d\n",
                      fragment, width, seed, modes[run], v->info.instrs_count,
                      v->info.nops_count, v->info.max_reg);
               ir3_shader_destroy(s);
            }
            free(reference);
            cases++;
         }
      }
   }
   printf("SH1 corpus passed: %u cases, %u compilations, %u changed shader binaries\n",
          cases, cases * 3, changed);
   assert(changed > 0);
   ir3_compiler_destroy(c);
   glsl_type_singleton_decref();
   return 0;
}
