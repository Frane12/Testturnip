from pathlib import Path
import shutil
R = Path('mesa/src/freedreno')
def edit(path, old, new):
    p = R / path
    s = p.read_text()
    assert s.count(old) == 1, (path, old[:100], s.count(old))
    p.write_text(s.replace(old, new, 1))
shutil.copyfile('patches/frane_mesa_26319_memory_audit.h', R/'vulkan/frane_mesa_26319_memory_audit.h')
edit('vulkan/tu_device.h', '   uint32_t frane_stage_nir_cache_inserts;', '   uint32_t frane_stage_nir_cache_inserts;\n   uint32_t frane_stage_nir_cache_bytes;')
edit('vulkan/tu_device.cc', '      p_atomic_set(&device->frane_stage_nir_cache_inserts, 0);', '      p_atomic_set(&device->frane_stage_nir_cache_inserts, 0);\n      p_atomic_set(&device->frane_stage_nir_cache_bytes, 0);')
edit('vulkan/tu_shader.cc', '#include "frane_mesa_2635_shader_pipeline.h"', '#include "frane_mesa_2635_shader_pipeline.h"\n#include "frane_mesa_26319_memory_audit.h"\n#include "nir/nir_serialize.h"\n#include "util/blob.h"')
helper = '''static void
frane_26319_add_nir(struct tu_device *device, const void *key,
                    uint32_t key_size, const nir_shader *nir)
{
   if (p_atomic_read_relaxed(&device->frane_stage_nir_cache_bytes) >=
       FRANE_26319_NIR_BUDGET)
      return;

   struct blob blob;
   blob_init(&blob);
   nir_serialize(&blob, nir, false);
   if (blob.out_of_memory || blob.size > FRANE_26319_NIR_MAX_BLOB) {
      blob_finish(&blob);
      return;
   }
   const uint32_t charge = blob.size + key_size +
      sizeof(struct vk_raw_data_cache_object) + 16u;
   if (!frane_26319_reserve_bytes(&device->frane_stage_nir_cache_bytes,
                                 charge)) {
      blob_finish(&blob);
      return;
   }
   struct vk_raw_data_cache_object *obj = vk_raw_data_cache_object_create(
      &device->vk, key, key_size, blob.data, blob.size);
   blob_finish(&blob);
   if (!obj) {
      p_atomic_add(&device->frane_stage_nir_cache_bytes, -charge);
      return;
   }
   struct vk_pipeline_cache_object *base = &obj->base;
   struct vk_pipeline_cache_object *cached = vk_pipeline_cache_add_object(
      device->frane_stage_nir_cache, base);
   if (cached != base)
      p_atomic_add(&device->frane_stage_nir_cache_bytes, -charge);
   vk_pipeline_cache_object_unref(&device->vk, cached);
}

'''
edit('vulkan/tu_shader.cc', 'static void\ninit_ir3_nir_options', helper+'static void\ninit_ir3_nir_options')
edit('vulkan/tu_shader.cc', '''               vk_pipeline_cache_add_nir(device->frane_stage_nir_cache,
                                         frane_nir_key,
                                         BLAKE3_KEY_LEN + 1,
                                         nir[stage]);''', '''               frane_26319_add_nir(device, frane_nir_key,
                                     BLAKE3_KEY_LEN + 1, nir[stage]);''')
edit('vulkan/tu_autotune.cc', '#include "frane_mesa_26318_a810_smart_gmem.h"', '#include "frane_mesa_26318_a810_smart_gmem.h"\n#include "frane_mesa_26319_memory_audit.h"')
edit('vulkan/tu_autotune.cc', '   frane_2634_gmem_state frane_gmem_runtime_state {};', '   frane_2634_gmem_state frane_gmem_runtime_state {};\n   frane_26319_gmem_freshness frane_gmem_freshness {};')
edit('vulkan/tu_autotune.cc', '''               frane_gmem_runtime_state = frane_2634_update_gmem_state(
                  frane_gmem_runtime_state, sys, gm,''', '''               frane_gmem_runtime_state = frane_26319_update_gmem(
                  frane_gmem_runtime_state, frane_gmem_freshness, sys, gm,''')
edit('vulkan/tu_autotune.cc', '''      if (cached &&
          hot_slot->hash.load(std::memory_order_acquire) == key.hash)''', '''      if (cached && cached->hash == key.hash &&
          cached->frane_2637_hot_pinned.load(std::memory_order_acquire))''')
edit('vulkan/tu_autotune.cc', '''            const auto layout =
               frane_2634_eval_layout(gmem_runtime_input->layout);
            const auto runtime_state''', '''            const auto runtime_state''')
edit('vulkan/tu_autotune.cc', '''            } else {
               runtime_decision = frane_2634_decide_gmem_runtime(''', '''            } else {
               const auto layout =
                  frane_2634_eval_layout(gmem_runtime_input->layout);
               runtime_decision = frane_2634_decide_gmem_runtime(''')
edit('ir3/ir3_sched.c', '      int live_growth = live_effect(n->instr);', '      int live_growth = ctx->compiler->frane_26317_adaptive_sched ?\n         live_effect(n->instr) : 0;')
edit('vulkan/tu_device.cc', 'Frane Mesa 26.3.18 A810 SMART-GMEM EXP / Mesa ', 'Frane Mesa 26.3.19 A810 MEMORY-AUDIT / Mesa ')
print('26.3.19 memory audit applied')
edit('vulkan/tu_knl_kgsl.cc',
     '(convert_ts_to_fd || num_fds > 0) && count + 1u > STACK_POLL_FDS',
     '(convert_ts_to_fd || num_fds > 0) && count >= STACK_POLL_FDS')
