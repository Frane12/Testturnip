from pathlib import Path
import os,subprocess,tempfile
v=Path('mesa/src/freedreno/vulkan')
s=(v/'tu_autotune.cc').read_text()
a=s.index('tu_autotune::rp_key::rp_key(const struct tu_render_pass *pass,')
b=s.index('tu_autotune::rp_key::rp_key(const rp_key &key,',a)
body=s[a:b]
pre=r'''
#include <cstdint>
#include <cassert>
#include <cstring>
#include <array>
#include <vector>
#include <cstdio>
#define PACKED __attribute__((packed))
#define XXH_INLINE_ALL
#include "util/xxhash.h"
#include "frane_a830_gmem_safety.h"
struct image { uint64_t id; };
struct view { uint32_t offset; };
struct attachment { struct image *image; struct view view; };
struct tu_device { uint64_t id; };
struct area { struct {int32_t x,y;} offset; struct {uint32_t width,height;} extent; };
struct tu_cmd_buffer { tu_device *device; struct { area render_areas[1]; attachment **attachments; struct {uint32_t drawcall_count; uint32_t frane_qp1_vertices; bool frane_qp1_unknown;} rp; uint32_t gmem_layout;} state; };
struct tu_render_pass { uint32_t attachment_count; uint64_t autotune_hash; struct {bool load,store,load_stencil,store_stencil;} attachments[6]; };
struct tu_framebuffer {uint32_t width,height,layers;};
bool frane_26320_a830_gpu(const tu_device *d) {return frane_a830_target(d->id);}
bool qp1_enabled=false;
bool frane_a830_qp1_enabled(const tu_device *d) {return qp1_enabled && frane_a830_target(d->id);}
namespace tu_autotune {struct rp_key {uint64_t hash;rp_key(const tu_render_pass*,const tu_framebuffer*,const tu_cmd_buffer*);};}
'''
post=r'''
int main() {
 tu_device dev{0x44050001};image img{123};attachment att{&img,{8}};attachment *atts[6]{&att,&att,&att,&att,&att,&att};
 tu_render_pass pass{};pass.attachment_count=1;pass.autotune_hash=0x100000002;
 tu_framebuffer fb{1280,720,1};tu_cmd_buffer cmd{};cmd.device=&dev;cmd.state.render_areas[0].extent={1280,720};cmd.state.attachments=atts;cmd.state.rp.drawcall_count=100;
 auto hash=[&](){return tu_autotune::rp_key(&pass,&fb,&cmd).hash;};
 auto base=hash();assert(base==hash());
 cmd.state.render_areas[0].offset.x=1;assert(hash()!=base);cmd.state.render_areas[0].offset.x=0;
 cmd.state.render_areas[0].offset.y=1;assert(hash()!=base);cmd.state.render_areas[0].offset.y=0;
 cmd.state.render_areas[0].extent.width=1279;assert(hash()!=base);cmd.state.render_areas[0].extent.width=1280;
 cmd.state.render_areas[0].extent.height=719;assert(hash()!=base);cmd.state.render_areas[0].extent.height=720;
 pass.autotune_hash^=uint64_t(1)<<40;assert(hash()!=base);pass.autotune_hash^=uint64_t(1)<<40;
 pass.autotune_hash^=1;assert(hash()!=base);pass.autotune_hash^=1;
 cmd.state.rp.drawcall_count=127;assert(hash()==base);
 cmd.state.rp.drawcall_count=128;assert(hash()!=base);cmd.state.rp.drawcall_count=100;
 cmd.state.gmem_layout=1;assert(hash()!=base);cmd.state.gmem_layout=0;
 dev.id=0x44010000;auto other=hash();cmd.state.render_areas[0].extent.width=2;cmd.state.rp.drawcall_count=1;pass.autotune_hash=3;cmd.state.gmem_layout=1;assert(hash()==other);
 dev.id=0x44050001;
 for(unsigned n=0;n<=6;n++){pass.attachment_count=n;cmd.state.rp.drawcall_count=0;auto zero=hash();cmd.state.rp.drawcall_count=1;assert(hash()!=zero);cmd.state.rp.drawcall_count=UINT32_MAX;auto max=hash();assert(hash()==max);}
 qp1_enabled=true;cmd.state.rp.drawcall_count=2;cmd.state.rp.frane_qp1_vertices=6;auto qp=hash();
 cmd.state.rp.drawcall_count=3;assert(hash()!=qp);cmd.state.rp.drawcall_count=2;
 cmd.state.rp.frane_qp1_vertices=12;assert(hash()!=qp);cmd.state.rp.frane_qp1_vertices=6;
 cmd.state.rp.frane_qp1_unknown=true;assert(hash()!=qp);cmd.state.rp.frane_qp1_unknown=false;
 qp1_enabled=false;assert(hash()!=qp);
 puts("Actual Mesa rp_key constructor: PASS (scope isolation, draw buckets, zero/UINT32_MAX, stack/heap attachment capacity; mocked Vulkan objects)");
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'key.cpp';p.write_text(pre+body+post)
 subprocess.run(['g++','-std=c++17','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-Imesa/src','-I'+str(v),str(p),'-o',d+'/key'],check=True)
 env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1')
 subprocess.run([d+'/key'],env=env,check=True)
