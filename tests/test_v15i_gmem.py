#!/usr/bin/env python3
"""Compile and exercise the actual patched cost decision with minimal type stubs.

This checks arithmetic/branch boundaries, not GPU execution or Mesa ABI.
Run after applying the patch stack to ./mesa.
"""
from pathlib import Path
import subprocess
import tempfile

src = Path('mesa/src/freedreno/vulkan/tu_autotune.cc').read_text()
start = src.index('         uint64_t pass_pixel_count = 0;')
end = src.index('         bool select_sysmem', start)
body = src[start:end]
helpers = src[src.index('static bool\nfrane_a830_gmem_dev_enabled'):src.index('/** Configuration **/')]
preamble = r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#define MAX2(a,b) ((a) > (b) ? (a) : (b))
constexpr unsigned VK_SAMPLE_COUNT_1_BIT = 1;
const char *os_get_option(const char *key) { return std::getenv(key); }
struct physical { struct { uint64_t chip_id; } dev_id; };
struct tu_device { physical *physical_device; };
struct VkExtent2D { uint32_t width, height; };
struct Area { VkExtent2D extent; };
struct Subpass { unsigned samples = 1; };
struct Pass {
 unsigned num_views = 1, subpass_count = 1;
 unsigned sysmem_bandwidth_per_pixel = 106, gmem_bandwidth_per_pixel = 100;
 Subpass subpasses[2];
};
struct Framebuffer { unsigned layers = 1; };
struct State { bool per_layer_render_area = false; Pass *pass; Framebuffer *framebuffer; Area render_areas[2]; };
struct RP { unsigned drawcall_count = 12, drawcall_bandwidth_per_sample_sum = 0; };
struct Average { uint64_t value; uint64_t get() const { return value; } };
struct Result { uint64_t pixels, cost; bool candidate, sysmem; };
Result decide(State *cmd_state, Pass *pass, Framebuffer *framebuffer, RP *rp_state,
              bool frane_a830_gmem_bias, Average mean_samples_passed) {
'''
checks = r'''
 return {pass_pixel_count, gmem_bandwidth, a830_candidate, sysmem_bandwidth <= gmem_bandwidth};
}
int main(int argc, char **argv) {
 if (argc > 1) {
   physical pd{{std::strtoull(argv[1], nullptr, 0)}}; tu_device d{&pd};
   assert(frane_a830_gmem_dev_enabled(&d) == (std::string(argv[2]) == "1"));
   assert(frane_a830_gmem_bias_enabled() == (std::string(argv[3]) == "1"));
   return 0;
 }
 Pass p; Framebuffer f; State s{false, &p, &f, {{{1280,720}}, {{1280,720}}}}; RP rp;
 const uint64_t pixels = 1280u * 720u;
 auto run = [&](bool bias=true, uint64_t samples=2*1280u*720u) { return decide(&s,&p,&f,&rp,bias,{samples}); };
 assert(!run(false).candidate && run(false).sysmem);
 assert(run().candidate && !run().sysmem);
 assert(!run(true, 0).candidate);
 assert(!run(true, 2*pixels-1).candidate);
 rp.drawcall_count=11; assert(!run().candidate); rp.drawcall_count=12;
 p.subpasses[0].samples=4; assert(!run().candidate); p.subpasses[0].samples=1;
 p.subpass_count=2; assert(!run().candidate); p.subpass_count=1;
 f.layers=2; assert(!run().candidate); f.layers=1;
 p.num_views=2; assert(!run().candidate); p.num_views=1;
 s.per_layer_render_area=true; assert(!run().candidate); s.per_layer_render_area=false;
 s.render_areas[0].extent={0,720}; assert(!run().candidate);
 s.render_areas[0].extent={1920,1080}; assert(run(true,2*1920u*1080u).candidate);
 s.render_areas[0].extent={1921,1080}; assert(!run(true,2*1921u*1080u).candidate);
 s.render_areas[0].extent={65536,65536}; assert(run().pixels==4294967296ull && !run().candidate);
 s.render_areas[0].extent={1280,720};
 p.sysmem_bandwidth_per_pixel=100; assert(!run().candidate); p.sysmem_bandwidth_per_pixel=106;
 rp.drawcall_bandwidth_per_sample_sum=120;
 const uint64_t draw_cost=2*pixels*120/12;
 assert(run().cost == (pixels*100*21 + draw_cost*2)/20);
 assert(run(false).cost == (pixels*100*11 + draw_cost)/10);
}
'''
import os
with tempfile.TemporaryDirectory() as td:
    cc = Path(td)/'decision.cc'; exe=Path(td)/'decision'
    cc.write_text(preamble.replace('Result decide', helpers+'\nResult decide') + body + checks)
    subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(cc),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
    for chip in ('0x44050001','0x44050000','0xffff44050000','0x43050a01'):
        for dev in (None,'0','1'):
            for bias in (None,'0','1','invalid'):
                env={k:v for k,v in os.environ.items() if k not in ('TU_A830_GMEM_DEV','TU_A830_GMEM_BIAS')}
                if dev is not None: env['TU_A830_GMEM_DEV']=dev
                if bias is not None: env['TU_A830_GMEM_BIAS']=bias
                subprocess.run([str(exe),chip,str(int(chip!='0x43050a01' and dev!='0')),str(int(bias=='1'))],env=env,check=True)
print('PASS: actual C++ cost decision, large-area arithmetic, draw penalty, and 48 device/environment combinations')
