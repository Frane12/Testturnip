from pathlib import Path
import subprocess
s=Path('mesa/src/freedreno/vulkan/tu_pass.cc').read_text()
start=s.index('static void\nattachment_set_ops(')
end=s.index('\nstatic bool\nis_depth_stencil_resolve_enabled',start)
function=s[start:end]
bw_start=s.index("static void\ntu_render_pass_bandwidth_config(")
bw_end=s.index("\nstatic void\nfrane_ds1_prepare_pass",bw_start)
bandwidth=s[bw_start:bw_end]
shim=r'''
#include <cassert>
#include <cstdio>
#include <initializer_list>
#include <cstdlib>
#include "frane_ds1.h"
using VkAttachmentLoadOp = int;
using VkAttachmentStoreOp = int;
constexpr int VK_ATTACHMENT_LOAD_OP_LOAD=0,VK_ATTACHMENT_LOAD_OP_CLEAR=1,VK_ATTACHMENT_LOAD_OP_DONT_CARE=2,VK_ATTACHMENT_LOAD_OP_NONE_EXT=1000400000;
constexpr int VK_ATTACHMENT_STORE_OP_STORE=0,VK_ATTACHMENT_STORE_OP_DONT_CARE=1,VK_ATTACHMENT_STORE_OP_NONE_EXT=1000301000;
constexpr unsigned VK_IMAGE_ASPECT_COLOR_BIT=1,VK_IMAGE_ASPECT_DEPTH_BIT=2,VK_IMAGE_ASPECT_STENCIL_BIT=4,VK_ATTACHMENT_UNUSED=~0u;
constexpr int VK_FORMAT_D24_UNORM_S8_UINT=129,VK_FORMAT_D32_SFLOAT_S8_UINT=130,VK_FORMAT_S8_UINT=127,VK_FORMAT_D32_SFLOAT=126,VK_FORMAT_D16_UNORM=124;
struct tu_instance { struct { struct { bool dont_care_as_load=false; } debug; } drirc; };
struct tu_device { tu_instance *instance; };
struct tu_physical_device { struct { uint64_t chip_id=0; } dev_id; };
static bool debug_get_bool_option(const char*,bool){return !std::getenv("TEST_DS1_OFF");}
struct tu_render_pass_attachment {
 unsigned cpp=4,samples=1; bool will_be_resolved=false;
 int format=0;frane_ds1_ops frane_ds_ops{};unsigned remapped_clear_att=0,clear_mask=0;
 bool load=false,store=false,load_stencil=false,store_stencil=false;
};
struct tu_render_pass { unsigned attachment_count=0,gmem_bandwidth_per_pixel=0,sysmem_bandwidth_per_pixel=0;tu_render_pass_attachment *attachments=nullptr; };
static bool vk_format_has_depth(int f){return f!=VK_FORMAT_S8_UINT;}
static bool vk_format_has_stencil(int f){return f==127||f==129||f==130;}
static bool vk_format_is_depth_or_stencil(int){return true;}
#define unlikely(x) (x)
'''
main=r'''
int main(){
 tu_instance instance{};tu_device dev{&instance};unsigned count=0;
 for(bool workaround:{false,true}){
 instance.drirc.debug.dont_care_as_load=workaround;
 for(int fmt:{124,126,127,129,130})
 for(int dload:{0,1,2,1000400000}) for(int sload:{0,1,2,1000400000})
 for(int dstore:{0,1,1000301000}) for(int sstore:{0,1,1000301000}){
  tu_render_pass_attachment att{};att.format=fmt;
  attachment_set_ops(&dev,&att,dload,sload,dstore,sstore);
  const auto kind=fmt==129?FRANE_DS1_PACKED:fmt==130?FRANE_DS1_SPLIT:fmt==127?FRANE_DS1_STENCIL:FRANE_DS1_DEPTH;
  frane_ds1_emitted emitted{att.load,att.store,att.load_stencil,att.store_stencil,0};
  if(fmt==129||fmt==130){if(att.clear_mask&2)emitted.clear|=1;if(att.clear_mask&4)emitted.clear|=2;}
  else if(att.clear_mask)emitted.clear=fmt==127?2:1;
  assert(frane_ds1_ops_valid(kind,att.frane_ds_ops,emitted));
  if(fmt==129&&((dstore==1000301000&&sstore==0)||(sstore==1000301000&&dstore==0))) assert(att.load);
  ++count;
 }
 }
 for (uint64_t id:{UINT64_C(0x44010000),UINT64_C(0x43050a01)})
 for(unsigned loads=0;loads<4;++loads) for(unsigned stores=0;stores<4;++stores) for(unsigned clear=0;clear<4;++clear){
   tu_render_pass_attachment att{};att.format=130;att.load=loads&1;att.load_stencil=loads&2;att.store=stores&1;att.store_stencil=stores&2;
   att.clear_mask=((clear&1)?2:0)|((clear&2)?4:0);
   tu_physical_device phys{};phys.dev_id.chip_id=id;
   tu_render_pass pass{};pass.attachment_count=1;pass.attachments=&att;
   tu_render_pass_bandwidth_config(&pass,&phys);
   const bool active=id==UINT64_C(0x44010000)&&!std::getenv("TEST_DS1_OFF");
   const unsigned gmem=(att.load?4:0)+(att.store?4:0)+(active?((att.load_stencil?1:0)+(att.store_stencil?1:0)):0);
   const unsigned sys=active?((clear&1?4:0)+(clear&2?1:0)):(clear?4:0);
   assert(pass.gmem_bandwidth_per_pixel==gmem && pass.sysmem_bandwidth_per_pixel==sys);
 }
 std::printf("Actual Mesa attachment_set_ops: %u aspect/LOAD/CLEAR/STORE/NONE cases PASS\n",count);
}
'''
out=Path('/tmp/ds1-mesa-ops.cpp');out.write_text(shim+function+bandwidth+main)
subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-Imesa/src/freedreno/vulkan',str(out),'-o','/tmp/ds1-mesa-ops'],check=True)
subprocess.run(['/tmp/ds1-mesa-ops'],check=True)
import os
subprocess.run(['/tmp/ds1-mesa-ops'],check=True,env={**os.environ,'TEST_DS1_OFF':'1'})
print('Actual Mesa D32S8 bandwidth accounting: 256 scope/control/transfer combinations PASS')
a=Path('mesa/src/freedreno/vulkan/tu_autotune.cc').read_text()
assert 'frane_ds1_frontier_allowed(frane_ds1_enabled(), smart_owned,' in a
assert a.index('return forced("DS1 GMEM eligibility"')<a.index('rp_history_handle history_owner = find_or_create_rp_history(key);',a.index('tu_autotune::get_optimal_mode(struct tu_cmd_buffer'))
assert s.count('frane_ds1_prepare_pass(pass, device->physical_device);')==2
assert 'att->cond_load_allowed = false;' in s and 'att->cond_store_allowed = false;' in s
assert 'Generated-by' not in function
print('DS1 integration source checks PASS')
