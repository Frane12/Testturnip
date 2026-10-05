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
      b.shader->info.num_textures = 4;
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

static void reference_binary(const char *directory, unsigned fragment,
                             unsigned width, unsigned seed, unsigned mode,
                             const struct ir3_shader_variant *v)
{
   char path[4096];
   int n = snprintf(path, sizeof(path), "%s/shader-%u-%u-%u-%u.bin",
                    directory, fragment, width, seed, mode);
   assert(n > 0 && (size_t)n < sizeof(path));
#ifdef FRANE_SH2_BUILD
   FILE *file = fopen(path, "rb");
   assert(file);
   assert(fseek(file, 0, SEEK_END) == 0);
   long size = ftell(file);
   assert(size >= 0 && (unsigned long)size == v->info.size);
   rewind(file);
   void *data = malloc(v->info.size);
   assert(data);
   assert(fread(data, 1, v->info.size, file) == v->info.size);
   assert(memcmp(data, v->bin, v->info.size) == 0);
   free(data);
#else
   FILE *file = fopen(path, "wb");
   assert(file);
   assert(fwrite(v->bin, 1, v->info.size, file) == v->info.size);
#endif
   assert(fclose(file) == 0);
}

int main(int argc, char **argv)
{
   assert(argc == 2);
   setenv("MESA_SHADER_CACHE_DISABLE", "true", 1);
   glsl_type_singleton_init_or_ref();
   const struct fd_dev_id id = {.chip_id = UINT64_C(0xffff44010000)};
   const struct ir3_compiler_options opts = {};
   struct ir3_compiler *c = ir3_compiler_create(NULL, &id, fd_dev_info_raw(&id), &opts);
   assert(c && c->frane_26317_adaptive_sched);
   struct ir3_shader_options options = {};
   struct ir3_shader_key key = {};
#ifdef FRANE_SH2_BUILD
   const unsigned runs = 6;
   unsigned changed[3] = {0};
#else
   const unsigned runs = 2;
#endif
   unsigned cases = 0;
   for (unsigned fragment = 0; fragment < 2; fragment++) {
      for (unsigned width = 4; width <= (fragment ? 16u : 64u); width *= 2) {
         for (unsigned seed = 0; seed < 8; seed++) {
#ifdef FRANE_SH2_BUILD
            void *sh1 = NULL, *sh2 = NULL;
            size_t sh1_size = 0, sh2_size = 0;
#endif
            for (unsigned run = 0; run < runs; run++) {
               c->frane_sh1_mode = run == 0 ? 0 : 1;
               c->frane_sh1_threshold = 35;
#ifdef FRANE_SH2_BUILD
               c->frane_sh2_critical = run == 2 || run >= 4;
               c->frane_sh2_sfu = run == 3 || run >= 4;
               c->frane_sh2_sfu_window = 6;
#endif
               nir_shader *nir = make_shader(c, fragment, width, seed);
               nir_assign_io_var_locations(nir, nir_var_shader_in);
               nir_assign_io_var_locations(nir, nir_var_shader_out);
               ir3_nir_lower_io(nir);
               nir_shader_gather_info(nir, nir_shader_get_entrypoint(nir));
               ir3_finalize_nir(c, &options.nir_options, nir);
               nir_validate_shader(nir, "SH2 finalized");
               struct ir3_shader *s = ir3_shader_from_nir(c, nir, &options);
               struct ir3_shader_variant *v = ir3_shader_create_variant(s, &key, true);
               assert(v && v->bin && v->info.size > 0);
               if (run < 2)
                  reference_binary(argv[1], fragment, width, seed, run, v);
#ifdef FRANE_SH2_BUILD
               if (run == 1) {
                  sh1_size = v->info.size;
                  sh1 = malloc(sh1_size);
                  assert(sh1);
                  memcpy(sh1, v->bin, sh1_size);
               } else if (run >= 2 && run <= 4) {
                  changed[run - 2] += sh1_size != v->info.size ||
                     memcmp(sh1, v->bin, sh1_size) != 0;
                  if (run == 4) {
                     sh2_size = v->info.size;
                     sh2 = malloc(sh2_size);
                     assert(sh2);
                     memcpy(sh2, v->bin, sh2_size);
                  }
               } else if (run == 5) {
                  assert(sh2_size == v->info.size);
                  assert(memcmp(sh2, v->bin, sh2_size) == 0);
               }
#endif
               printf("stage=%u width=%u seed=%u config=%u instr=%u nop=%u reg=%d waves=%d ss=%u sy=%u stp=%u ldp=%u\n",
                      fragment, width, seed, run, v->info.instrs_count,
                      v->info.nops_count, v->info.max_reg, v->info.max_waves,
                      v->info.ss, v->info.sy, v->info.stp_count, v->info.ldp_count);
               ir3_shader_destroy(s);
            }
#ifdef FRANE_SH2_BUILD
            free(sh1);
            free(sh2);
#endif
            cases++;
         }
      }
   }
#ifdef FRANE_SH2_BUILD
   printf("SH2 corpus passed: %u cases, %u compilations, 128 baseline binaries identical; critical=%u sfu=%u both=%u changed binaries; SH2 repeats identical\n",
          cases, cases * runs, changed[0], changed[1], changed[2]);
   assert(changed[0] > 0 && changed[1] > 0 && changed[2] > 0);
#else
   printf("SH1/V38 references saved: %u cases, %u compilations\n", cases, cases * runs);
#endif
   ir3_compiler_destroy(c);
   glsl_type_singleton_decref();
   return 0;
}
