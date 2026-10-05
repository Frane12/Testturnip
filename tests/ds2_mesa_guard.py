from pathlib import Path
import os, subprocess, tempfile
root=Path(__file__).resolve().parents[1];mesa=root/'mesa';src=mesa/'src/freedreno/vulkan'
if not mesa.exists():
    mesa=root.parent/'mesa';src=mesa/'src/freedreno/vulkan'
with tempfile.TemporaryDirectory() as folder:
    base=Path(folder);name='src/freedreno/vulkan/tu_autotune.cc'
    p=base/name;p.parent.mkdir(parents=True)
    p.write_bytes(subprocess.check_output(['git','show','HEAD:'+name],cwd=mesa))
    for patch in ['s1-smart2-complete.patch','s1-smart-ds1.patch']:
        subprocess.run(['git','apply','--include='+name,str(root/'patches'/patch)],cwd=base,check=True)
    old=p.read_text()
new=(src/'tu_autotune.cc').read_text();pas=(src/'tu_pass.cc').read_text()
def guard(s,name):
    begin=s.index('static bool\nfrane_a810_gmem_pass_safe(')
    end=s.index('\nstatic tu_autotune::render_mode',begin)
    return s[begin:end].replace('frane_a810_gmem_pass_safe',name)
begin=pas.index('static void\nfrane_ds1_prepare_pass(')
end=pas.index('static void\nattachment_set_ops(',begin)
prepare=pas[begin:end]
shim=r'''
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <initializer_list>
#include "frane_ds1.h"
constexpr unsigned TU_GMEM_LAYOUT_COUNT=2,TU_GMEM_LAYOUT_AVOID_CCU=1,VK_SAMPLE_COUNT_1_BIT=1;
constexpr int VK_FORMAT_D24_UNORM_S8_UINT=129,VK_FORMAT_D32_SFLOAT_S8_UINT=130,VK_FORMAT_S8_UINT=127;
constexpr unsigned VK_IMAGE_ASPECT_DEPTH_BIT=2,VK_IMAGE_ASPECT_STENCIL_BIT=4;
#define MIN2(a,b) ((a)<(b)?(a):(b))
struct info_t{unsigned tile_align_w=32,tile_align_h=16;};
struct tu_physical_device{struct{uint64_t chip_id=0x44010000;}dev_id;info_t *info;unsigned usable_gmem_size_gmem=81920;struct{unsigned color_ccu_offset=49152;}config_gmem;};
struct tu_device{tu_physical_device *physical_device;};
struct tu_subpass{unsigned input_count=0,resolve_count=0,unresolve_count=0,multiview_mask=0,samples=1;bool resolve_depth_stencil=false,feedback_loop_color=false,feedback_loop_ds=false,feedback_invalidate=false,raster_order_attachment_access=false,custom_resolve=false;};
struct tu_render_pass_attachment{unsigned samples=1,first_subpass_idx=0,last_subpass_idx=0,cpp=4,clear_mask=0;int format=130;bool will_be_resolved=false,gmem=true,cond_load_allowed=false,cond_store_allowed=false,load=true,store=true,load_stencil=true,store_stencil=true;int32_t gmem_offset[2]={0,0},gmem_offset_stencil[2]={65536,32768};frane_ds1_ops frane_ds_ops{3,3,0,0,true};};
struct tu_render_pass{uint8_t frane_ds_flags=0,frane_ds_layout_mask=0;unsigned attachment_count=1,subpass_count=1,num_views=0,gmem_pixels[2]={16384,8192};bool has_fdm=false,has_layered_fdm=false,has_msrtss=false,has_cond_load_store=false;tu_subpass subpasses[1]{};tu_render_pass_attachment *attachments;};
struct extent_t{unsigned width=64,height=64;};struct area{struct{int x=0,y=0;}offset;extent_t extent;};
using VkRect2D=area;
struct tu_framebuffer{unsigned width=64,height=64,layers=1;};
struct tiling_t{bool possible=true;extent_t tile0;struct{extent_t tile_count;}vsc;};
struct tu_cmd_state{tiling_t *tiling;bool per_layer_render_area=false;unsigned gmem_layout=0;area render_areas[1];};
static bool vk_format_has_depth(int f){return f!=127;}
static bool vk_format_has_stencil(int f){return f==127||f==129||f==130;}
static bool frane_a810_gmem_safety_enabled(const tu_device *dev){return dev->physical_device->dev_id.chip_id==0x44010000||dev->physical_device->dev_id.chip_id==0xffff44010000;}
static bool frane_ds1_enabled(){return !std::getenv("TEST_DS1_OFF");}
static bool debug_get_bool_option(const char*,bool value){return value;}
'''
main=r'''
int main(){
 info_t info{};unsigned count=0,accepted=0;
 for(int format:{126,127,129,130})for(unsigned mask=0;mask<65536;++mask){
  tu_physical_device phys{};phys.info=&info;tu_device dev{&phys};
  tu_render_pass_attachment att{};att.format=format;
  if(format!=130)att.load_stencil=att.store_stencil=false;
  if(format==126)att.frane_ds_ops={1,1,0,0,true};
  if(format==127){att.frane_ds_ops={2,2,0,0,true};att.cpp=1;}
  tu_render_pass p{};p.attachments=&att;auto &sp=p.subpasses[0];
  sp.input_count=bool(mask&1);sp.resolve_count=bool(mask&2);sp.feedback_loop_ds=bool(mask&4);
  sp.samples=mask&8?2:1;att.cond_load_allowed=mask&16;att.will_be_resolved=mask&32;
  att.first_subpass_idx=mask&64?1:0;att.gmem_offset_stencil[0]=mask&128?61440:65536;
  phys.usable_gmem_size_gmem=mask&256?0:81920;p.num_views=mask&512?1:0;
  p.has_fdm=mask&1024;sp.raster_order_attachment_access=mask&2048;
  frane_ds1_prepare_pass(&p,&phys);
  tu_framebuffer fb{};fb.layers=mask&4096?2:1;
  tiling_t tile{};tile.possible=!(mask&8192);tu_cmd_state cmd{};cmd.tiling=&tile;
  cmd.render_areas[0].offset.x=mask&16384?1:0;cmd.render_areas[0].extent.width=mask&32768?32:64;
  for(unsigned layout=0;layout<2;++layout){
   cmd.gmem_layout=layout;
   const bool a=old_guard(&dev,&cmd,&p,&fb),b=new_guard(&dev,&cmd,&p,&fb);
   assert(a==b);accepted+=b;++count;
  }
 }
 std::printf("Actual Mesa DS1->DS2 safety guard equivalence: %u cases, %u accepted PASS (%s)\n",count,accepted,frane_ds1_enabled()?"DS1 ON":"DS1 OFF");
}
'''
cpp=Path('/tmp/ds2-guard.cpp');cpp.write_text(shim+prepare+guard(old,'old_guard')+guard(new,'new_guard')+main)
subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(src),str(cpp),'-o','/tmp/ds2-guard'],check=True)
subprocess.run(['/tmp/ds2-guard'],check=True)
subprocess.run(['/tmp/ds2-guard'],check=True,env={**os.environ,'TEST_DS1_OFF':'1'})
assert 'if (mode == render_mode::GMEM && !ds1_precheck &&' in new
assert '(*rp_ctx)->frane_adaptive_sample = adaptive_owned;' in new
assert new.index('if (entry.frane_adaptive_sample)')<new.index('if (entry.frane_smart_sample &&')
print('Adaptive ownership, feedback route and reused safety check integration PASS')
