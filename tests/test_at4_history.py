from pathlib import Path
import os, subprocess, sys, tempfile
root=Path(sys.argv[1]).resolve();out=Path(tempfile.mkdtemp(prefix='at4-history-'))
src=(root/'src/freedreno/vulkan/tu_autotune.cc').read_text()
start=src.index('tu_autotune::rp_key::rp_key(const struct tu_render_pass *pass,')
end=src.index('tu_autotune::rp_key::rp_key(const rp_key &key',start)
constructor=src[start:end].rstrip()
code=r'''
#include <cstdint>
#include <cassert>
#include <array>
#include <vector>
#include <cstring>
#include <cstdio>
#define PACKED __attribute__((packed))
#define XXH_INLINE_ALL
#include "util/xxhash.h"
#include "frane_a810_at4.h"
constexpr unsigned VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT=1;
constexpr unsigned VK_COMMAND_BUFFER_USAGE_SIMULTANEOUS_USE_BIT=4;
struct tu_image {uint64_t id=1;};
struct tu_image_view {tu_image *image;struct {uint32_t offset=0;} view;};
struct tu_render_pass_attachment {bool load=true,store=true,load_stencil=false,store_stencil=false;};
struct tu_render_pass {unsigned attachment_count=1;tu_render_pass_attachment *attachments;unsigned subpass_count=1,num_views=0;};
struct tu_framebuffer {uint32_t width=1280,height=720,layers=1;};
struct VkRect2D {struct {int32_t x=0,y=0;} offset;struct {uint32_t width=1280,height=720;} extent;};
struct tiling {bool possible=true;struct {uint32_t width=256,height=256;} tile0;struct {struct {uint32_t width=5,height=3;} tile_count;} vsc;};
struct tu_autotune {
 enum class algorithm {PROFILED,PROFILED_IMM};enum class mod_flag {PREEMPT_OPTIMIZE};
 struct config_t {bool plain=true,imm=false,preempt=false;bool is_enabled(algorithm a)const{return a==algorithm::PROFILED?plain:imm;}bool test(mod_flag)const{return preempt;}};
 struct {config_t value;config_t load()const{return value;}} active_config;
 struct rp_key {uint64_t hash;rp_key(const tu_render_pass *,const tu_framebuffer *,const struct tu_cmd_buffer *);};
};
struct tu_device {tu_autotune *autotune;uint64_t id=0x44010000;};
static bool at4=true;
static bool frane_a810_s1at4_enabled(const tu_device *d){return at4&&(d->id==0x44010000||d->id==0xffff44010000);}
static bool frane_a810_lean_profiled(){return true;}
static bool frane_a810_v24_fastpath(){return true;}
struct tu_cmd_buffer {tu_device *device;unsigned usage_flags=1;struct {tu_image_view **attachments;struct {uint32_t drawcall_count=16,frane_at4_vertices=100;bool frane_at4_geometry_unknown=false,has_tess=false;uint64_t drawcall_bandwidth_per_sample_sum=128;} rp;struct tiling *tiling;bool per_layer_render_area=false;VkRect2D render_areas[16];} state;};
CONSTRUCTOR
int main(){
 tu_image img;tu_image_view view{&img};tu_image_view *views[]={&view};tu_render_pass_attachment att;tu_render_pass pass{1,&att};tu_framebuffer fb;tu_autotune tune;tu_device dev{&tune};tu_cmd_buffer cmd;cmd.device=&dev;cmd.state.attachments=views;tiling grid;cmd.state.tiling=&grid;
 auto hash=[&](){return tu_autotune::rp_key(&pass,&fb,&cmd).hash;};
 const auto original=hash();assert(hash()==original);
 cmd.state.rp.drawcall_count=47;assert(hash()!=original);cmd.state.rp.drawcall_count=16;
 cmd.state.rp.frane_at4_vertices=10000;assert(hash()!=original);cmd.state.rp.frane_at4_vertices=100;
 cmd.state.rp.frane_at4_geometry_unknown=true;assert(hash()!=original);cmd.state.rp.frane_at4_geometry_unknown=false;
 cmd.state.render_areas[0].extent.width=640;assert(hash()!=original);cmd.state.render_areas[0].extent.width=1280;
 cmd.state.render_areas[0].offset.x=-4;assert(hash()!=original);cmd.state.render_areas[0].offset.x=0;
 pass.subpass_count=2;assert(hash()!=original);pass.subpass_count=1;
 grid.tile0.width=512;assert(hash()!=original);grid.tile0.width=256;
 at4=false;const auto legacy=hash();assert(legacy!=original);
 cmd.state.rp.drawcall_count=47;cmd.state.render_areas[0].extent.width=640;pass.subpass_count=2;assert(hash()==legacy);
 cmd.state.rp.drawcall_count=16;cmd.state.render_areas[0].extent.width=1280;pass.subpass_count=1;
 at4=true;dev.id=0x830;assert(hash()==legacy);dev.id=0x44010000;
 tune.active_config.value.imm=true;assert(hash()==legacy);tune.active_config.value.imm=false;
 tune.active_config.value.preempt=true;assert(hash()==legacy);tune.active_config.value.preempt=false;
 cmd.usage_flags=0;assert(hash()==legacy);cmd.usage_flags=5;assert(hash()==legacy);cmd.usage_flags=1;
 dev.id=0xffff44010000;assert(hash()==original);
 att.store=false;assert(hash()!=original);
 puts("actual RP key: draw/geometry/area/subpass/tiling separation, stability, A810 and legacy gates: PASS");
}
'''.replace('CONSTRUCTOR',constructor)
(out/'history.cpp').write_text(code)
subprocess.run(['g++','-std=c++17','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(root/'src'),'-I'+str(root/'src/freedreno/vulkan'),str(out/'history.cpp'),'-o',str(out/'history')],check=True)
subprocess.run([str(out/'history')],env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'),check=True)
