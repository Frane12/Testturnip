#!/usr/bin/env python3
"""Frane Mesa 26.3.5 A810 SHADER-PIPELINE EXP.

Layered on green 26.3.4. Goal: reduce first-use pipeline/shader CPU stalls
without changing NIR lowering, IR3 optimization, generated shader code, WSI or
GMEM policy.

Main experiment:
  * bounded, RAM-only per-stage intermediate-NIR cache on A810;
  * probe every compiled-shader stage even after an earlier miss;
  * never reinsert/re-serialize stages that already came from cache;
  * use cache-object unref for mixed cached/new shader failure cleanup;
  * avoid pipeline/stage clock reads unless creation feedback is requested.
"""
from pathlib import Path
import shutil

ROOT = Path("mesa")
V = ROOT / "src/freedreno/vulkan"

def edit(rel, old, new, label):
    p = ROOT / rel
    s = p.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"26.3.5 SHADER-PIPELINE source drift: {label}: expected 1 anchor, saw {n}: {old[:180]!r}")
    p.write_text(s.replace(old, new, 1))
    print(f"26.3.5 SHADER-PIPELINE PASS {label}", flush=True)

shutil.copyfile("patches/frane_mesa_2635_shader_pipeline.h",
                V / "frane_mesa_2635_shader_pipeline.h")

# ---------------------------------------------------------------------------
# Device-local RAM-only intermediate NIR cache. It is deliberately separate
# from the app/final pipeline cache and never performs disk lookup/write.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_device.h",
'''   /* Backup in-memory cache to be used if the app doesn't provide one */
   struct vk_pipeline_cache *mem_cache;''',
'''   /* Backup in-memory cache to be used if the app doesn't provide one */
   struct vk_pipeline_cache *mem_cache;

   /* 26.3.5 A810: bounded session-local intermediate NIR cache.
    * This cache is created with skip_disk_cache=true so a first-use lookup
    * cannot block on filesystem I/O. */
   struct vk_pipeline_cache *frane_stage_nir_cache;
   uint32_t frane_stage_nir_cache_inserts;''',
"device fields for bounded RAM-only stage NIR cache")

edit("src/freedreno/vulkan/tu_device.cc",
'''#include "tu_device.h"''',
'''#include "tu_device.h"
#include "frane_mesa_2635_shader_pipeline.h"''',
"device includes shader-pipeline policy")

edit("src/freedreno/vulkan/tu_device.cc",
'''   device->mem_cache = vk_pipeline_cache_create(&device->vk, &pcc_info,
                                                NULL);
   if (!device->mem_cache) {
      result = VK_ERROR_OUT_OF_HOST_MEMORY;
      vk_startup_errorf(device->instance, result, "create pipeline cache failed");
      goto fail_pipeline_cache;
   }

   tu_cs_init(&device->sub_cs, device, TU_CS_MODE_SUB_STREAM, 1024, "device sub cs");''',
'''   device->mem_cache = vk_pipeline_cache_create(&device->vk, &pcc_info,
                                                NULL);
   if (!device->mem_cache) {
      result = VK_ERROR_OUT_OF_HOST_MEMORY;
      vk_startup_errorf(device->instance, result, "create pipeline cache failed");
      goto fail_pipeline_cache;
   }

   if (frane_2635_is_a810_chip(physical_device->dev_id.chip_id) &&
       debug_get_bool_option("TU_A810_STAGE_NIR_CACHE", true)) {
      struct vk_pipeline_cache_create_info frane_nir_info = {};
      frane_nir_info.skip_disk_cache = true;
      frane_nir_info.force_enable = true;
      device->frane_stage_nir_cache =
         vk_pipeline_cache_create(&device->vk, &frane_nir_info, NULL);
      /* Optional optimization: allocation failure falls back to stock path. */
      p_atomic_set(&device->frane_stage_nir_cache_inserts, 0);
   }

   tu_cs_init(&device->sub_cs, device, TU_CS_MODE_SUB_STREAM, 1024, "device sub cs");''',
"create optional A810 RAM-only NIR cache")

edit("src/freedreno/vulkan/tu_device.cc",
'''fail_perfcntrs_pass_entries_alloc:
   tu_cs_finish(&device->sub_cs);
   vk_pipeline_cache_destroy(device->mem_cache, &device->vk.alloc);
fail_pipeline_cache:''',
'''fail_perfcntrs_pass_entries_alloc:
   tu_cs_finish(&device->sub_cs);
   if (device->frane_stage_nir_cache)
      vk_pipeline_cache_destroy(device->frane_stage_nir_cache,
                                &device->vk.alloc);
   vk_pipeline_cache_destroy(device->mem_cache, &device->vk.alloc);
fail_pipeline_cache:''',
"destroy optional NIR cache on device-create failure")

edit("src/freedreno/vulkan/tu_device.cc",
'''   ir3_compiler_destroy(device->compiler);

   vk_pipeline_cache_destroy(device->mem_cache, &device->vk.alloc);''',
'''   ir3_compiler_destroy(device->compiler);

   if (device->frane_stage_nir_cache)
      vk_pipeline_cache_destroy(device->frane_stage_nir_cache,
                                &device->vk.alloc);
   vk_pipeline_cache_destroy(device->mem_cache, &device->vk.alloc);''',
"destroy optional NIR cache on normal device teardown")

# ---------------------------------------------------------------------------
# Compile function: accept per-stage intermediate keys and make creation
# feedback timing genuinely optional.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_shader.h",
'''                   struct tu_pipeline_layout *layout,
                   const unsigned char *pipeline_blake3,
                   struct tu_shader **shaders,''',
'''                   struct tu_pipeline_layout *layout,
                   const unsigned char *pipeline_blake3,
                   const unsigned char *stage_nir_keys,
                   struct tu_shader **shaders,''',
"tu_compile_shaders declaration accepts stage NIR keys")

edit("src/freedreno/vulkan/tu_shader.cc",
'''#include "tu_shader.h"''',
'''#include "tu_shader.h"
#include "frane_mesa_2635_shader_pipeline.h"''',
"shader compiler includes 26.3.5 policy")

edit("src/freedreno/vulkan/tu_shader.cc",
'''                   struct tu_pipeline_layout *layout,
                   const unsigned char *pipeline_blake3,
                   struct tu_shader **shaders,''',
'''                   struct tu_pipeline_layout *layout,
                   const unsigned char *pipeline_blake3,
                   const unsigned char *stage_nir_keys,
                   struct tu_shader **shaders,''',
"tu_compile_shaders definition accepts stage NIR keys")

old = '''      int64_t stage_start = os_time_get_nano();

      nir[stage] = tu_spirv_to_nir(device, mem_ctx, pipeline_flags,
                                   stage_info, &keys[stage], stage);
      if (!nir[stage]) {
         result = VK_ERROR_OUT_OF_HOST_MEMORY;
         goto fail;
      }

      stage_feedbacks[stage].flags = VK_PIPELINE_CREATION_FEEDBACK_VALID_BIT;
      stage_feedbacks[stage].duration += os_time_get_nano() - stage_start;'''
new = '''      const int64_t stage_start =
         stage_feedbacks ? os_time_get_nano() : 0;

      bool frane_nir_hit = false;
      const unsigned char *frane_nir_key =
         stage_nir_keys ?
         stage_nir_keys + stage * (BLAKE3_KEY_LEN + 1) : NULL;

      if (frane_nir_key && device->frane_stage_nir_cache) {
         nir[stage] = vk_pipeline_cache_lookup_nir(
            device->frane_stage_nir_cache,
            frane_nir_key, BLAKE3_KEY_LEN + 1,
            ir3_get_compiler_options(device->compiler),
            NULL, mem_ctx);
         frane_nir_hit = nir[stage] != NULL;
      }

      if (!nir[stage]) {
         nir[stage] = tu_spirv_to_nir(device, mem_ctx, pipeline_flags,
                                      stage_info, &keys[stage], stage);
         if (!nir[stage]) {
            result = VK_ERROR_OUT_OF_HOST_MEMORY;
            goto fail;
         }

         /* Keep the cache bounded: once 384 unique insert reservations have
          * been consumed, lookups continue but new NIR blobs are not retained.
          * Races may consume a few reservations for duplicate keys, which is
          * intentionally conservative for RAM usage. */
         if (frane_nir_key && device->frane_stage_nir_cache &&
             p_atomic_read_relaxed(&device->frane_stage_nir_cache_inserts) <
                FRANE_2635_STAGE_NIR_MAX_ENTRIES) {
            const uint32_t slot =
               p_atomic_inc_return(&device->frane_stage_nir_cache_inserts);
            if (slot <= FRANE_2635_STAGE_NIR_MAX_ENTRIES) {
               vk_pipeline_cache_add_nir(device->frane_stage_nir_cache,
                                         frane_nir_key,
                                         BLAKE3_KEY_LEN + 1,
                                         nir[stage]);
            }
         }
      }

      if (stage_feedbacks) {
         stage_feedbacks[stage].flags =
            VK_PIPELINE_CREATION_FEEDBACK_VALID_BIT;
         stage_feedbacks[stage].duration +=
            os_time_get_nano() - stage_start;
      }
      (void) frane_nir_hit;'''
edit("src/freedreno/vulkan/tu_shader.cc", old, new,
     "RAM-only stage NIR lookup/add and optional frontend timing")

edit("src/freedreno/vulkan/tu_shader.cc",
'''      int64_t stage_start = os_time_get_nano();

      tu_lower_nir(device, nir[stage], &keys[stage], &ir3_key, &info[stage]);

      stage_feedbacks[stage].duration += os_time_get_nano() - stage_start;''',
'''      const int64_t stage_start =
         stage_feedbacks ? os_time_get_nano() : 0;

      tu_lower_nir(device, nir[stage], &keys[stage], &ir3_key, &info[stage]);

      if (stage_feedbacks)
         stage_feedbacks[stage].duration +=
            os_time_get_nano() - stage_start;''',
"skip NIR-lowering clock reads without creation feedback")

edit("src/freedreno/vulkan/tu_shader.cc",
'''      int64_t stage_start = os_time_get_nano();

      unsigned char shader_blake3[BLAKE3_KEY_LEN + 1];''',
'''      const int64_t stage_start =
         stage_feedbacks ? os_time_get_nano() : 0;

      unsigned char shader_blake3[BLAKE3_KEY_LEN + 1];''',
"skip backend stage-start clock without creation feedback")

edit("src/freedreno/vulkan/tu_shader.cc",
'''      stage_feedbacks[stage].duration += os_time_get_nano() - stage_start;
   }

   ralloc_free(mem_ctx);''',
'''      if (stage_feedbacks)
         stage_feedbacks[stage].duration +=
            os_time_get_nano() - stage_start;
   }

   ralloc_free(mem_ctx);''',
"skip backend duration clock without creation feedback")

edit("src/freedreno/vulkan/tu_shader.cc",
'''      if (shaders[stage]) {
         tu_shader_destroy(device, shaders[stage]);
      }''',
'''      if (shaders[stage]) {
         /* Works for both a fresh refcount-1 shader and a lookup reference
          * returned by the pipeline cache. */
         vk_pipeline_cache_object_unref(&device->vk,
                                         &shaders[stage]->base);
      }''',
"mixed cached/new shader failure path uses cache-object ownership")

# ---------------------------------------------------------------------------
# Graphics pipeline: compute stage-specific keys once, probe all compiled
# stages instead of breaking on the first miss, and avoid reinserting hits.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_pipeline.cc",
'''#include "tu_pipeline.h"''',
'''#include "tu_pipeline.h"
#include "frane_mesa_2635_shader_pipeline.h"''',
"pipeline includes 26.3.5 policy")

# Creation feedback lookup moves ahead of the timer so normal DXVK pipelines
# don't pay a clock read solely for an unused extension.
edit("src/freedreno/vulkan/tu_pipeline.cc",
'''   int64_t pipeline_start = os_time_get_nano();

   const VkPipelineCreationFeedbackCreateInfo *creation_feedback =
      vk_find_struct_const(builder->create_info->pNext, PIPELINE_CREATION_FEEDBACK_CREATE_INFO);''',
'''   const VkPipelineCreationFeedbackCreateInfo *creation_feedback =
      vk_find_struct_const(builder->create_info->pNext,
                           PIPELINE_CREATION_FEEDBACK_CREATE_INFO);
   const int64_t pipeline_start =
      creation_feedback ? os_time_get_nano() : 0;''',
"graphics pipeline clock only when creation feedback is requested")

# Stage NIR keys are computed after all graphics-specific tu_shader_key fields
# (multiview/FDM/etc.) are finalized.
edit("src/freedreno/vulkan/tu_pipeline.cc",
'''   unsigned char pipeline_blake3[BLAKE3_KEY_LEN];
   tu_hash_shaders(pipeline_blake3, builder->create_flags, stage_infos, nir,
                   &builder->layout, keys, builder->state);''',
'''   unsigned char stage_nir_blake3[MESA_SHADER_STAGES][BLAKE3_KEY_LEN + 1] = {};
   const bool frane_stage_nir_enabled =
      builder->device->frane_stage_nir_cache != NULL && !executable_info;

   if (frane_stage_nir_enabled) {
      for (mesa_shader_stage stage = MESA_SHADER_VERTEX;
           stage < MESA_SHADER_STAGES;
           stage = (mesa_shader_stage) (stage + 1)) {
         if (!stage_infos[stage])
            continue;

         tu_hash_compute(stage_nir_blake3[stage],
                         builder->create_flags,
                         stage_infos[stage],
                         &builder->layout,
                         &keys[stage]);
         stage_nir_blake3[stage][BLAKE3_KEY_LEN] =
            FRANE_2635_STAGE_NIR_KEY_SUFFIX;
      }
   }

   unsigned char pipeline_blake3[BLAKE3_KEY_LEN];
   tu_hash_shaders(pipeline_blake3, builder->create_flags, stage_infos, nir,
                   &builder->layout, keys, builder->state);''',
"compute safe per-stage intermediate NIR keys")

old = '''      cache_hit = true;
      bool application_cache_hit = true;

      unsigned char shader_blake3[BLAKE3_KEY_LEN + 1];
      memcpy(shader_blake3, pipeline_blake3, sizeof(pipeline_blake3));

      for (mesa_shader_stage stage = MESA_SHADER_VERTEX; stage < ARRAY_SIZE(nir);
           stage = (mesa_shader_stage) (stage + 1)) {
         if (stage_infos[stage] || nir[stage]) {
            bool shader_application_cache_hit;
            shader_blake3[BLAKE3_KEY_LEN] = (unsigned char) stage;
            shaders[stage] =
               tu_pipeline_cache_lookup(builder->cache, &shader_blake3,
                                        sizeof(shader_blake3),
                                        &shader_application_cache_hit);
            if (!shaders[stage]) {
               cache_hit = false;
               break;
            }
            application_cache_hit &= shader_application_cache_hit;
         }
      }'''
new = '''      frane_2635_stage_probe_state frane_probe {};

      unsigned char shader_blake3[BLAKE3_KEY_LEN + 1];
      memcpy(shader_blake3, pipeline_blake3, sizeof(pipeline_blake3));

      for (mesa_shader_stage stage = MESA_SHADER_VERTEX; stage < ARRAY_SIZE(nir);
           stage = (mesa_shader_stage) (stage + 1)) {
         if (stage_infos[stage] || nir[stage]) {
            bool shader_application_cache_hit = false;
            shader_blake3[BLAKE3_KEY_LEN] = (unsigned char) stage;
            shaders[stage] =
               tu_pipeline_cache_lookup(builder->cache, &shader_blake3,
                                        sizeof(shader_blake3),
                                        &shader_application_cache_hit);

            /* Deliberately do not break on a miss. Later stages may still be
             * available, which lets tu_compile_shaders() skip their IR3
             * backend and makes mixed cache ownership explicit. */
            frane_2635_record_stage_probe(
               frane_probe, stage, shaders[stage] != NULL,
               shader_application_cache_hit);
         }
      }

      cache_hit = frane_probe.all_hit;
      const bool application_cache_hit = frane_probe.application_hit;
      const uint64_t frane_shader_cache_hit_mask = frane_probe.hit_mask;'''
edit("src/freedreno/vulkan/tu_pipeline.cc", old, new,
     "probe all shader stages and retain partial cache hits")

# The hit mask must remain available after the local lookup block.
# Hoist declaration before the block, then assign inside.
edit("src/freedreno/vulkan/tu_pipeline.cc",
'''   bool cache_hit = false;

   struct tu_shader_key keys[ARRAY_SIZE(stage_infos)] = { };''',
'''   bool cache_hit = false;
   uint64_t frane_shader_cache_hit_mask = 0;

   struct tu_shader_key keys[ARRAY_SIZE(stage_infos)] = { };''',
"hoist compiled-stage cache-hit mask")

edit("src/freedreno/vulkan/tu_pipeline.cc",
'''      const uint64_t frane_shader_cache_hit_mask = frane_probe.hit_mask;''',
'''      frane_shader_cache_hit_mask = frane_probe.hit_mask;''',
"publish compiled-stage cache-hit mask")

edit("src/freedreno/vulkan/tu_pipeline.cc",
'''                                  &builder->layout,
                                  pipeline_blake3,
                                  shaders,
                                  executable_info ? nir_initial_disasm : NULL,''',
'''                                  &builder->layout,
                                  pipeline_blake3,
                                  frane_stage_nir_enabled ?
                                     &stage_nir_blake3[0][0] : NULL,
                                  shaders,
                                  executable_info ? nir_initial_disasm : NULL,''',
"pass per-stage NIR keys into compiler")

edit("src/freedreno/vulkan/tu_pipeline.cc",
'''                                  pipeline->executables_mem_ctx,
                                  retain_nir ? post_link_nir : NULL,
                                  stage_feedbacks);''',
'''                                  pipeline->executables_mem_ctx,
                                  retain_nir ? post_link_nir : NULL,
                                  creation_feedback ? stage_feedbacks : NULL);''',
"stage timing disabled when app did not request feedback")

old = '''      for (mesa_shader_stage stage = MESA_SHADER_VERTEX; stage < ARRAY_SIZE(nir);
           stage = (mesa_shader_stage) (stage + 1)) {
         if (!nir[stage])
            continue;

         shaders[stage] = tu_pipeline_cache_insert(builder->cache, shaders[stage]);
      }'''
new = '''      for (mesa_shader_stage stage = MESA_SHADER_VERTEX; stage < ARRAY_SIZE(nir);
           stage = (mesa_shader_stage) (stage + 1)) {
         if (!nir[stage] ||
             frane_2635_stage_was_cached(frane_shader_cache_hit_mask, stage))
            continue;

         shaders[stage] =
            tu_pipeline_cache_insert(builder->cache, shaders[stage]);
      }'''
edit("src/freedreno/vulkan/tu_pipeline.cc", old, new,
     "do not reserialize/reinsert shader stages already found in cache")

edit("src/freedreno/vulkan/tu_pipeline.cc",
'''   pipeline_feedback.duration = os_time_get_nano() - pipeline_start;
   if (creation_feedback) {
      *creation_feedback->pPipelineCreationFeedback = pipeline_feedback;''',
'''   if (creation_feedback) {
      pipeline_feedback.duration = os_time_get_nano() - pipeline_start;
      *creation_feedback->pPipelineCreationFeedback = pipeline_feedback;''',
"graphics pipeline end clock only with feedback")

# ---------------------------------------------------------------------------
# Compute path: no NIR cache experiment here yet, only remove unused timing.
# It has little cross-pipeline stage reuse and is kept as a control path.
# ---------------------------------------------------------------------------
edit("src/freedreno/vulkan/tu_pipeline.cc",
'''   const VkPipelineCreationFeedbackCreateInfo *creation_feedback =
      vk_find_struct_const(pCreateInfo->pNext, PIPELINE_CREATION_FEEDBACK_CREATE_INFO);

   int64_t pipeline_start = os_time_get_nano();''',
'''   const VkPipelineCreationFeedbackCreateInfo *creation_feedback =
      vk_find_struct_const(pCreateInfo->pNext,
                           PIPELINE_CREATION_FEEDBACK_CREATE_INFO);

   const int64_t pipeline_start =
      creation_feedback ? os_time_get_nano() : 0;''',
"compute pipeline clock only when feedback requested")

edit("src/freedreno/vulkan/tu_pipeline.cc",
'''   pipeline_feedback.duration = os_time_get_nano() - pipeline_start;

   if (creation_feedback) {
      *creation_feedback->pPipelineCreationFeedback = pipeline_feedback;''',
'''   if (creation_feedback) {
      pipeline_feedback.duration = os_time_get_nano() - pipeline_start;
      *creation_feedback->pPipelineCreationFeedback = pipeline_feedback;''',
"compute pipeline end clock only with feedback")

# Protect all previous experimental behavior and verify no compiler optimizer
# knob was changed.
pipeline = (V / "tu_pipeline.cc").read_text()
shader = (V / "tu_shader.cc").read_text()
device = (V / "tu_device.cc").read_text()
for needle in (
   "frane_2635_record_stage_probe",
   "vk_pipeline_cache_lookup_nir",
   "vk_pipeline_cache_add_nir",
   "skip_disk_cache = true",
   "FRANE_2635_STAGE_NIR_MAX_ENTRIES",
):
    if needle not in pipeline + shader + device:
        raise SystemExit(f"26.3.5 missing expected feature: {needle}")
if "ir3_optimize_options" not in shader:
    raise SystemExit("26.3.5 unexpected shader source drift")
print("26.3.5 SHADER-PIPELINE PASS compile path changed without IR3 optimizer policy change", flush=True)

edit("src/freedreno/vulkan/tu_device.cc",
     "Frane Mesa 26.3.4 A810 GMEM-RUNTIME EXP / Mesa ",
     "Frane Mesa 26.3.5 A810 SHADER-PIPELINE EXP / Mesa ",
     "experimental driver identity")

print("Frane Mesa 26.3.5 A810 SHADER-PIPELINE EXP applied", flush=True)
