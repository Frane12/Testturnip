from pathlib import Path
import os
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
mesa = root / 'mesa'
if not mesa.exists():
    mesa = root.parent / 'mesa'
source = (mesa / 'src/vulkan/runtime/vk_pipeline_cache.c').read_text()
start = source.index('#define VK_HOT_OBJECT_SLOTS')
end = source.index('static bool\nobject_keys_equal(', start)
functions = source[start:end]
mem_start = source.index('struct vk_pipeline_cache_object *\nvk_pipeline_cache_lookup_object_in_memory(')
mem_end = source.index('/* cache->lock must be held', mem_start)
memory_lookup = source[mem_start:mem_end]

shim = r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <thread>
#include <vector>
#define p_atomic_read(v) __atomic_load_n((v), __ATOMIC_ACQUIRE)
#define p_atomic_read_relaxed(v) __atomic_load_n((v), __ATOMIC_RELAXED)
#define p_atomic_set(v,i) __atomic_store_n((v),(i),__ATOMIC_RELEASE)
struct vk_pipeline_cache_object_ops {};
struct vk_pipeline_cache_object {
 const vk_pipeline_cache_object_ops *ops = nullptr;
 std::atomic<uint32_t> refs { 1 };
 const void *key_data;
 uint32_t key_size;
};
struct set_entry { const void *key; };
struct set { std::vector<set_entry> entries; };
struct vk_pipeline_cache {
 const vk_pipeline_cache_object_ops *hot_object_ops = nullptr;
 vk_pipeline_cache_object **hot_objects = nullptr;
 set *object_cache = nullptr;
 std::mutex mutex {};
 std::atomic<unsigned> locks {0};
};
static vk_pipeline_cache_object *vk_pipeline_cache_object_ref(void *p) {
 auto *o=static_cast<vk_pipeline_cache_object *>(p);
 ++o->refs; return o;
}
static uint32_t object_key_hash(const vk_pipeline_cache_object *) { return 13; }
static void vk_pipeline_cache_lock(vk_pipeline_cache *c) { ++c->locks; c->mutex.lock(); }
static void vk_pipeline_cache_unlock(vk_pipeline_cache *c) { c->mutex.unlock(); }
static set_entry *_mesa_set_search_pre_hashed(set *s,uint32_t,const vk_pipeline_cache_object *key) {
 for(auto &e:s->entries) {
  const auto *o=static_cast<const vk_pipeline_cache_object *>(e.key);
  if(o->key_size==key->key_size && !memcmp(o->key_data,key->key_data,key->key_size))return &e;
 }
 return nullptr;
}
'''
test = r'''
int main() {
 vk_pipeline_cache_object_ops shader, raw;
 uint8_t a[33] {}, b[33] {}, c[32] {};
 a[32]=1; b[32]=2;
 vk_pipeline_cache_object oa {&shader, {1}, a, sizeof(a)};
 vk_pipeline_cache_object ob {&shader, {1}, b, sizeof(b)};
 vk_pipeline_cache_object oc {&shader, {1}, c, sizeof(c)};
 vk_pipeline_cache_object blob {&raw, {1}, a, sizeof(a)};
 vk_pipeline_cache_object *slots[VK_HOT_OBJECT_SLOTS] {};
 vk_pipeline_cache enabled { &shader, slots }, disabled {}, other;
 assert(!vk_pipeline_cache_hot_lookup(nullptr,&oa,13,&shader));
 assert(!vk_pipeline_cache_hot_lookup(&disabled,&oa,13,&shader));
 vk_pipeline_cache_hot_publish(&enabled,&oa,13);
 assert(oa.refs==1);
 auto *found=vk_pipeline_cache_hot_lookup(&enabled,&oa,13,&shader);
 assert(found==&oa && oa.refs==2); --oa.refs;
 assert(!vk_pipeline_cache_hot_lookup(&enabled,&ob,13,&shader));
 assert(!vk_pipeline_cache_hot_lookup(&enabled,&oc,13,&shader));
 assert(!vk_pipeline_cache_hot_lookup(&enabled,&oa,13,&raw));
 assert(!vk_pipeline_cache_hot_lookup(&other,&oa,13,&shader));
 vk_pipeline_cache_hot_publish(&enabled,&blob,13);
 assert(slots[13]==&oa);
 vk_pipeline_cache_hot_publish(&enabled,&ob,13+VK_HOT_OBJECT_SLOTS);
 assert(slots[13]==&ob && oa.refs==1 && ob.refs==1);
 assert(!vk_pipeline_cache_hot_lookup(&enabled,&oa,13,&shader));
 std::atomic<unsigned> hits {0};
 std::vector<std::thread> readers;
 for(unsigned i=0;i<8;i++) readers.emplace_back([&] {
    for(unsigned n=0;n<100000;n++) {
       auto *o=vk_pipeline_cache_hot_lookup(&enabled,&oa,13,&shader);
       if(o) { assert(o==&oa); --o->refs; ++hits; }
       o=vk_pipeline_cache_hot_lookup(&enabled,&ob,13,&shader);
       if(o) { assert(o==&ob); --o->refs; ++hits; }
    }
 });
 for(unsigned n=0;n<100000;n++)
    vk_pipeline_cache_hot_publish(&enabled,n&1?&oa:&ob,13);
 for(auto &t:readers)t.join();
 assert(oa.refs==1 && ob.refs==1 && hits>0);
 set table;
 table.entries.push_back({&oa});
 table.entries.push_back({&blob});
 enabled.object_cache=&table;
 slots[13]=nullptr;
 bool hit=false;
 found=vk_pipeline_cache_lookup_object_in_memory(&enabled,a,sizeof(a),&shader,&hit);
 assert(found==&oa && hit && enabled.locks==1); --oa.refs;
 found=vk_pipeline_cache_lookup_object_in_memory(&enabled,a,sizeof(a),&shader,&hit);
 assert(found==&oa && hit && enabled.locks==1); --oa.refs;
 hit=true;
 assert(!vk_pipeline_cache_lookup_object_in_memory(&enabled,b,sizeof(b),&shader,&hit) && !hit);
 set raw_table;
 raw_table.entries.push_back({&blob});
 other.object_cache=&raw_table;
 hit=true;
 assert(!vk_pipeline_cache_lookup_object_in_memory(&other,a,sizeof(a),&shader,&hit) && !hit);
 assert(!vk_pipeline_cache_lookup_object_in_memory(&disabled,a,sizeof(a),&shader,&hit));
 assert(oa.refs==1 && blob.refs==1);
 printf("PASS: extracted Mesa hot-cache functions: exact stage/size/type/cache isolation, collision replacement, no extra ownership, 1.6M concurrent lookups; slots=%u bytes=%zu\n",VK_HOT_OBJECT_SLOTS,sizeof(slots));
}
'''

with tempfile.TemporaryDirectory() as td:
    p = Path(td)
    (p / 'cache.cpp').write_text(shim + functions + memory_lookup + test)
    sanitizer = os.environ.get('SC1_SANITIZER', 'address,undefined')
    subprocess.run(['g++', '-std=c++17', '-O2', '-g', '-pthread', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=' + sanitizer, str(p / 'cache.cpp'), '-o', str(p / 'cache')], check=True)
    subprocess.run([str(p / 'cache')], check=True)

assert 'cache->object_cache && !cache->weak_ref && info->hot_object_ops' in source
assert 'info->hot_object_ops != &vk_raw_data_cache_object_ops' in source
assert 'vk_zalloc2(&device->alloc, pAllocator,' in source
assert 'vk_free2(&cache->base.device->alloc, pAllocator, cache->hot_objects)' in source
print('PASS: weak/disabled/raw caches excluded, allocation failure falls back, cache-local allocation freed with original callbacks')
