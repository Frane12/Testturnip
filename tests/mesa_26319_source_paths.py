from pathlib import Path
import subprocess, tempfile, os
src = Path('mesa/src/freedreno/vulkan/tu_shader.cc').read_text()
a=src.index('static void\nfrane_26319_add_nir')
b=src.index('static void\ninit_ir3_nir_options', a)
helper=src[a:b]
aut=Path('mesa/src/freedreno/vulkan/tu_autotune.cc').read_text()
a=aut.index('      if (cached &&',aut.index('tu_autotune::find_rp_history'))
b=aut.index('         return rp_history_handle',a)
hit=aut[a:b].strip()
kg=Path('mesa/src/freedreno/vulkan/tu_knl_kgsl.cc').read_text()
a=kg.index('   if ((convert_ts_to_fd || num_fds > 0) &&')
b=kg.index(' {',a)
heap=kg[a:b].strip()
pre=r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <atomic>
#include "frane_mesa_26319_memory_audit.h"
#define p_atomic_read_relaxed(p) __atomic_load_n(p,__ATOMIC_RELAXED)
#define p_atomic_add(p,n) __atomic_add_fetch(p,n,__ATOMIC_RELAXED)
struct vk_device {};
struct vk_pipeline_cache_object {};
struct vk_raw_data_cache_object { vk_pipeline_cache_object base; };
struct vk_pipeline_cache {};
struct nir_shader {};
struct tu_device { vk_device vk; uint32_t frane_stage_nir_cache_bytes=0; vk_pipeline_cache *frane_stage_nir_cache=nullptr; };
struct blob { bool out_of_memory; size_t size; void *data; };
static int mode=0, live_blobs=0, live_objects=0;
static vk_pipeline_cache_object existing;
void blob_init(blob *b) { *b={false,0,nullptr}; live_blobs++; }
void nir_serialize(blob *b,const nir_shader *,bool) {
 b->out_of_memory=mode==1; b->size=mode==2 ? FRANE_26319_NIR_MAX_BLOB+1u : 1024u;
}
void blob_finish(blob *) { live_blobs--; }
vk_raw_data_cache_object *vk_raw_data_cache_object_create(vk_device *,const void *,size_t,const void *,size_t) {
 if(mode==3) return nullptr; live_objects++; return new vk_raw_data_cache_object;
}
vk_pipeline_cache_object *vk_pipeline_cache_add_object(vk_pipeline_cache *,vk_pipeline_cache_object *o) {
 if(mode==4) { delete reinterpret_cast<vk_raw_data_cache_object *>(o); live_objects--; return &existing; }
 return o;
}
void vk_pipeline_cache_object_unref(vk_device *,vk_pipeline_cache_object *o) {
 if(o!=&existing) { delete reinterpret_cast<vk_raw_data_cache_object *>(o); live_objects--; }
}
'''
post=r'''
int main() {
 tu_device device; nir_shader nir;
 for(mode=1;mode<=4;mode++) {
  frane_26319_add_nir(&device,"key",3,&nir);
  assert(device.frane_stage_nir_cache_bytes==0);
  assert(live_blobs==0 && live_objects==0);
 }
 mode=0;
 frane_26319_add_nir(&device,"key",3,&nir);
 assert(device.frane_stage_nir_cache_bytes==1024+3+sizeof(vk_raw_data_cache_object)+16);
 device.frane_stage_nir_cache_bytes=FRANE_26319_NIR_BUDGET-1;
 frane_26319_add_nir(&device,"key",3,&nir);
 assert(device.frane_stage_nir_cache_bytes==FRANE_26319_NIR_BUDGET-1);
 assert(live_blobs==0 && live_objects==0);
 struct History { uint64_t hash; std::atomic<bool> frane_2637_hot_pinned{false}; } history{64};
 struct Slot { std::atomic<uint64_t> hash{0}; } slot;
 auto *hot_slot=&slot; (void)hot_slot;
 auto *cached=&history;
 struct { uint64_t hash; } key{0};
 auto matches=[&] { HIT return true; return false; };
 assert(!matches());
 key.hash=64;
 assert(!matches());
 history.frane_2637_hot_pinned=true;
 assert(matches());
 history.hash=0;key.hash=0;
 assert(matches());
 const uint32_t STACK_POLL_FDS=16;
 bool convert_ts_to_fd=false; uint32_t num_fds=1, count=0;
 auto needs_heap=[&] { HEAP return true; return false; };
 count=15; assert(!needs_heap());
 count=16; assert(needs_heap());
 count=UINT32_MAX; assert(needs_heap());
 num_fds=0; assert(!needs_heap());
 convert_ts_to_fd=true; assert(needs_heap());
}
'''.replace('HIT',hit).replace('HEAP',heap)
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'source.cpp';p.write_text(pre+helper+post)
 exe=Path(d)/'source-test'
 subprocess.run(['g++','-std=c++17','-O1','-g','-fsanitize=address,undefined','-I'+str(Path('patches').resolve()),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True)
print('PASS: actual NIR insertion cleanup/budget/duplicate paths and actual hot-cache zero-hash publication predicate')
