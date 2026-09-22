#!/usr/bin/env python3
"""Compile actual patched Mesa functions against small fake kernel/BO backends.
These tests cover CPU ownership and sync selection, NOT GPU rendering.
"""
from pathlib import Path
import os, subprocess, tempfile
M=Path('mesa/src/freedreno/vulkan')
def fn(src, marker):
 start=src.index(marker); opening=src.index('{',start); depth=1; i=opening+1
 while depth:
  depth += (src[i]=='{')-(src[i]=='}'); i+=1
 return src[start:i]
def run(name,src):
 with tempfile.TemporaryDirectory(prefix='v16-') as p:
  source=Path(p)/(name+'.cc'); exe=Path(p)/name; source.write_text(src)
  subprocess.run(['g++','-std=c++17','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-fno-pie','-no-pie',str(source),'-o',str(exe)],check=True)
  subprocess.run([str(exe)],check=True,env={**os.environ,'ASAN_OPTIONS':os.environ.get('ASAN_OPTIONS','detect_leaks=1')})
 print(name+': PASS',flush=True)
k=(M/'tu_knl_kgsl.cc').read_text()
run('kgsl_sync',r'''
#include <cassert>
#include <cstdint>
#include <map>
#include <set>
#include <cstdlib>
#define UNREACHABLE(x) abort()
enum State { KGSL_SYNCOBJ_STATE_SIGNALED, KGSL_SYNCOBJ_STATE_UNSIGNALED, KGSL_SYNCOBJ_STATE_TS, KGSL_SYNCOBJ_STATE_FD };
struct Queue { int id; };
struct kgsl_syncobj { State state; Queue *queue=nullptr; uint32_t timestamp=0; int fd=-1; };
using Deps=std::set<int>;
std::map<int,Deps> fds;
int next_fd=100;
int makefd(Deps deps) {int f=next_fd++; fds[f]=deps; return f;}
int os_dupfd_cloexec(int f) {assert(fds.count(f)); return makefd(fds.at(f));}
void kgsl_syncobj_init(kgsl_syncobj *s,bool signaled) {*s={signaled?KGSL_SYNCOBJ_STATE_SIGNALED:KGSL_SYNCOBJ_STATE_UNSIGNALED};}
void kgsl_syncobj_reset(kgsl_syncobj *s) {if(s->state==KGSL_SYNCOBJ_STATE_FD) assert(fds.erase(s->fd)==1); kgsl_syncobj_init(s,false);}
uint32_t max_ts(uint32_t a,uint32_t b) {return (int32_t)(a-b)>=0?a:b;}
int kgsl_syncobj_ts_to_fd(const kgsl_syncobj *s) {assert(s->state==KGSL_SYNCOBJ_STATE_TS && s->queue); return makefd({s->queue->id*1000+(int)s->timestamp});}
int sync_merge_close(const char*,int a,int b,bool close_b) {assert(fds.count(a)&&fds.count(b)); Deps deps=fds.at(a); deps.insert(fds.at(b).begin(),fds.at(b).end()); fds.erase(a); if(close_b) fds.erase(b); return makefd(deps);}
'''+fn(k,'static struct kgsl_syncobj\nkgsl_syncobj_merge')+r'''
int main() {
 Queue q1{1},q2{2};
 kgsl_syncobj a{KGSL_SYNCOBJ_STATE_TS,&q1,11}, b{KGSL_SYNCOBJ_STATE_TS,&q2,12};
 kgsl_syncobj c{KGSL_SYNCOBJ_STATE_FD,nullptr,0,makefd({999})};
 auto test=[&](const kgsl_syncobj *x,const kgsl_syncobj *y,Deps expected) {
  size_t prior=fds.size(); const kgsl_syncobj* in[]={x,y}; auto out=kgsl_syncobj_merge(in,2);
  assert(out.state==KGSL_SYNCOBJ_STATE_FD && fds.at(out.fd)==expected);
  kgsl_syncobj_reset(&out); assert(fds.size()==prior); assert(fds.count(c.fd));
 };
 test(&a,&b,{1011,2012}); test(&a,&c,{1011,999}); test(&c,&a,{1011,999}); test(&c,&c,{999});
 kgsl_syncobj later{KGSL_SYNCOBJ_STATE_TS,&q1,15}; const kgsl_syncobj* same[]={&a,&later};
 auto out=kgsl_syncobj_merge(same,2); assert(out.state==KGSL_SYNCOBJ_STATE_TS && out.timestamp==15);
 const kgsl_syncobj* none[]={}; out=kgsl_syncobj_merge(none,0); assert(out.state==KGSL_SYNCOBJ_STATE_SIGNALED);
 kgsl_syncobj_reset(&c); assert(fds.empty());
}
''')
s=(M/'tu_suballoc.cc').read_text()
run('suballocator',r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <initializer_list>
#include <cstdlib>
#define MAX2(a,b) ((a)>(b)?(a):(b))
using VkResult=int;
constexpr int VK_SUCCESS=0, VK_ERROR_OUT_OF_HOST_MEMORY=-1, MAP_FAILURE=-42;
enum tu_bo_alloc_flags { FLAGS=0 };
struct DevId { uint64_t chip_id; };
struct Physical {DevId dev_id;};
struct tu_device {Physical *physical_device;};
struct tu_bo {int refcnt=1; uint32_t size; uint64_t iova=4096; void *map=nullptr;};
struct tu_suballocator {tu_device *dev; uint32_t default_size; tu_bo_alloc_flags flags; tu_bo *bo; uint32_t next_offset=0; tu_bo *cached_bo; const char *name;};
struct tu_suballoc_bo {tu_bo *bo=nullptr; uint64_t iova=0; uint32_t size=0;};
int live=0; bool fail_map=false;
const char* os_get_option(const char*) {return nullptr;}
int p_atomic_read(int *p) {return *p;}
uint32_t align(uint32_t n,uint32_t a) {return (n+a-1)&~(a-1);}
void tu_bo_finish(tu_device*,tu_bo *b) {assert(b->refcnt>0); if(!--b->refcnt){--live;delete b;}}
tu_bo* tu_bo_get_ref(tu_bo *b) {assert(b->refcnt>0); ++b->refcnt;return b;}
VkResult tu_bo_init_new(tu_device*,void*,tu_bo **p,uint32_t n,tu_bo_alloc_flags,const char*) {*p=new tu_bo;(*p)->size=n;++live;return VK_SUCCESS;}
VkResult tu_bo_map(tu_device*,tu_bo *b,void*) {if(fail_map)return MAP_FAILURE;b->map=b;return VK_SUCCESS;}
'''+ '\n'.join(fn(s,x) for x in ['void\ntu_bo_suballocator_init','void\ntu_bo_suballocator_finish','VkResult\ntu_suballoc_bo_alloc','void\ntu_suballoc_bo_free']) +r'''
int main() {
 Physical p{{0x44050001ull}};tu_device dev{&p};tu_suballocator pool{};tu_suballoc_bo out{};
 tu_bo_suballocator_init(&pool,&dev,65536,FLAGS,"autotune_suballoc");
 fail_map=true; assert(tu_suballoc_bo_alloc(&out,&pool,16,16)==MAP_FAILURE);
 assert(!pool.bo && live==0);tu_bo_suballocator_finish(&pool);assert(live==0);
 fail_map=false; assert(tu_suballoc_bo_alloc(&out,&pool,16,16)==VK_SUCCESS);
 tu_suballoc_bo_free(&pool,&out);tu_bo_suballocator_finish(&pool);assert(live==0);
 for(const char *name:{"autotune_suballoc","pipeline_suballoc"}) {
  tu_bo_suballocator_init(&pool,&dev,65536,FLAGS,name);
  auto *large=new tu_bo; large->size=131072;++live;out.bo=large;
  tu_suballoc_bo_free(&pool,&out);assert(live==0 && !pool.cached_bo);
  auto *small=new tu_bo;small->size=65536;++live;out.bo=small;
  tu_suballoc_bo_free(&pool,&out);assert(live==1 && pool.cached_bo==small);
  tu_bo_suballocator_finish(&pool);assert(live==0);
  tu_bo_suballocator_init(&pool,&dev,65536,FLAGS,name);
  auto *busy=new tu_bo;busy->size=131072;busy->refcnt=2;++live;out.bo=busy;
  tu_suballoc_bo_free(&pool,&out);assert(live==1 && busy->refcnt==1 && !pool.cached_bo);
  tu_bo_finish(&dev,busy);assert(live==0);
 }
}
'''.replace('#include',' #include'))
a=(M/'tu_autotune.cc').read_text()
handle=fn(a,'struct tu_autotune::rp_history_handle')+';'
# Test exact ownership methods, with a minimal history rather than the GPU statistics.
run('history_ownership',r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <utility>
#define ASSERTED
uint64_t os_time_get_nano() {return 100;}
struct tu_autotune {
 struct rp_history {std::atomic<uint32_t> refcount{0};std::atomic<uint64_t> last_use_ts{0};};
 struct rp_history_handle;
};
'''+handle+'\n'+fn(a,'tu_autotune::rp_history_handle &\ntu_autotune::rp_history_handle::operator=')+'\n'+fn(a,'tu_autotune::rp_history_handle::~rp_history_handle')+'\n'+fn(a,'tu_autotune::rp_history_handle::rp_history_handle(rp_history &history)')+r'''
int main() {
 tu_autotune::rp_history a,b;
 {tu_autotune::rp_history_handle x(a),y(b);
  assert(a.refcount==1 && b.refcount==1); x=std::move(y);
  assert(a.refcount==0 && b.refcount==1 && !y);
  x=std::move(x);assert(b.refcount==1);
  tu_autotune::rp_history_handle z(std::move(x));assert(!x && b.refcount==1);
 }assert(a.refcount==0 && b.refcount==0);
}
''')
print('Actual Mesa functions passed ASan/UBSan regression tests. GPU behavior untested.')
