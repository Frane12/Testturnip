from pathlib import Path
import subprocess, tempfile, os
v=Path('mesa/src/freedreno/vulkan')
s=(v/'tu_cmd_buffer.cc').read_text()
start=s.index('frane_a830_qp1_input\nfrane_a830_qp1_get_input(')
end=s.index('static bool\nuse_sysmem_rendering',start)
actual=s[start:end]
pre=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
#include "frane_a830_qp1.h"
#include "frane_a830_gmem_safety.h"
struct tu_device {uint64_t id=0x44050001;};
struct extent {uint32_t width=2,height=2;};
struct tu_vsc_config {extent tile_count;bool binning_possible=true,binning_useful=true;};
struct tu_tiling_config {tu_vsc_config vsc;bool possible=true;};
struct tu_framebuffer {uint32_t layers=1;};
struct subpass {bool depth_used=false,stencil_used=false;};
struct pass {bool has_fdm=false,has_msrtss=false;unsigned num_views=1,subpass_count=1;subpass subpasses[1];};
struct rp {unsigned drawcall_count=3,frane_qp1_vertices=18;bool frane_qp1_unknown=false,has_tess=false,xfb_used=false,has_prim_generated_query_in_rp=false,has_vtx_stats_query_in_rp=false,has_zpass_done_sample_count_write_in_rp=false,draw_cs_writes_to_cond_pred=false;};
struct tu_cmd_buffer {tu_device *device;struct {tu_framebuffer *framebuffer;tu_tiling_config *tiling;struct pass *pass;struct rp rp;bool xfb_query_running_before_rp=false,prim_generated_query_running_before_rp=false,vtx_stats_query_running_before_rp=false,per_layer_render_area=false;unsigned prim_counters_running=0,gmem_layout=0,gmem_layout_divisor=0;} state;};
bool enabled=true,diagnostic=false;unsigned debug=0;
enum {FORCEBIN=1,NOBIN=2,FORCE_CONCURRENT_BINNING=4};
#define TU_DEBUG(x) ((debug & (x))!=0)
#define perf_debug(...) ((void)0)
#define mesa_logi(...) ((void)0)
bool debug_get_bool_option(const char*,bool){return diagnostic;}
bool frane_a830_qp1_enabled(const tu_device*d){return enabled&&frane_a830_target(d->id);}
const tu_tiling_config *tu_framebuffer_get_tiling_config(tu_framebuffer*,tu_device*,pass*,unsigned,unsigned){extern tu_tiling_config tiling;return &tiling;}
const tu_vsc_config *tu_vsc_config(tu_cmd_buffer*,const tu_tiling_config*t){return &t->vsc;}
tu_tiling_config tiling;
'''
post=r'''
int main(){
 tu_device dev;tu_framebuffer fb;pass p;tu_cmd_buffer cmd{};cmd.device=&dev;cmd.state.framebuffer=&fb;cmd.state.pass=&p;cmd.state.tiling=&tiling;
 auto reset=[&]{cmd.state.rp={};debug=0;enabled=true;p={};fb={};tiling={};cmd.state.xfb_query_running_before_rp=false;cmd.state.vtx_stats_query_running_before_rp=false;cmd.state.prim_generated_query_running_before_rp=false;cmd.state.prim_counters_running=0;cmd.state.per_layer_render_area=false;dev.id=0x44050001;};
 auto bin=[&]{return use_hw_binning(&cmd);};
 assert(!bin());enabled=false;assert(bin());enabled=true;
 for(auto id:{uint64_t(0x44050000),uint64_t(0x44050001),uint64_t(0xffff44050000),uint64_t(0xffff44050001)}) {dev.id=id;assert(!bin());}
 dev.id=0x44010000;assert(bin());reset();
 cmd.state.rp.frane_qp1_vertices=4096;assert(bin());reset();
 cmd.state.rp.frane_qp1_unknown=true;assert(bin());reset();
 cmd.state.rp.xfb_used=true;assert(bin());reset();
 cmd.state.rp.has_prim_generated_query_in_rp=true;assert(bin());reset();
 cmd.state.rp.has_vtx_stats_query_in_rp=true;assert(bin());reset();
 cmd.state.rp.has_zpass_done_sample_count_write_in_rp=true;assert(bin());reset();
 cmd.state.xfb_query_running_before_rp=true;assert(bin());reset();
 cmd.state.prim_generated_query_running_before_rp=true;assert(bin());reset();
 cmd.state.vtx_stats_query_running_before_rp=true;assert(bin());reset();
 cmd.state.prim_counters_running=1;assert(bin());reset();
 cmd.state.rp.draw_cs_writes_to_cond_pred=true;assert(bin());reset();
 for(unsigned bit:{FORCEBIN,NOBIN,FORCE_CONCURRENT_BINNING}){debug=bit;assert(bin());reset();}
 p.subpasses[0].depth_used=true;assert(bin());reset();
 p.subpasses[0].stencil_used=true;assert(bin());reset();
 p.has_msrtss=true;assert(bin());reset();p.has_fdm=true;assert(bin());reset();
 p.subpass_count=2;assert(bin());reset();p.num_views=2;assert(bin());reset();
 fb.layers=2;assert(bin());reset();cmd.state.per_layer_render_area=true;assert(bin());reset();
 tiling.vsc.binning_possible=false;assert(!bin());reset();tiling.vsc.binning_useful=false;assert(!bin());reset();
 cmd.state.rp.drawcall_count=2;cmd.state.rp.frane_qp1_vertices=6;
 assert(frane_a830_qp1_tune_small(frane_a830_qp1_get_input(&cmd),1280*720,4,16));
 puts("Actual Mesa QP1 eligibility and use_hw_binning functions: PASS (A830 IDs, off switch, hazard/override gates; mocked Vulkan objects)");
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'runtime.cpp';p.write_text(pre+actual+post)
 subprocess.run(['g++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(v),str(p),'-o',d+'/test'],check=True)
 subprocess.run([d+'/test'],env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0',UBSAN_OPTIONS='halt_on_error=1'),check=True)
a=(v/'tu_autotune.cc').read_text();h=(v/'tu_cmd_buffer.h').read_text()
assert 'frane_a830_qp1_tune_small(frane_a830_qp1_get_input(cmd_buffer)' in a
assert a.index('frane_a830_qp1_tune_small(frane_a830_qp1_get_input(cmd_buffer)')<a.index('if (ignore_small_rp)')
assert 'uint64_t(draw_count) * instance_count' in s
assert 'instance_count == UINT32_MAX' in s
assert 'dst->frane_qp1_unknown |= src->frane_qp1_unknown' in s
assert 'memset(&cmd_buffer->state.rp, 0, sizeof(cmd_buffer->state.rp))' in s
assert 'frane-a830-qp1-v1:' in a
assert '0x51503101u' in a
assert 'TU_FRANE_A830_QP1_LOG' in s and 'TU_FRANE_A830_QP1_LOG' in a
assert 'uint32_t frane_qp1_vertices' in h
f=s[s.index('static bool\nuse_sysmem_rendering'):s.index('/* Optimization: there is no reason to load gmem')]
assert f.index('A830 GMEM disabled by TU_FRANE_A830_GMEM=0')<f.index('if (TU_DEBUG(GMEM))')
assert 'Mark all tiles as visible' in s
assert 'tu7_cb_disable_reason(!use_hw_binning, cmd, "hw binning disabled")' in s
print('QP1 dataflow/reset/merge/indirect/cache/visibility/CB guards: PASS')
