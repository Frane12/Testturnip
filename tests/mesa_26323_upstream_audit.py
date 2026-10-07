#!/usr/bin/env python3
"""Differential tests of actual patched policy and compiler cache identity."""
from pathlib import Path
import os
import re
import subprocess
import tempfile

r = Path('mesa/src/freedreno').resolve()
v = r / 'vulkan'
smart = Path('/tmp/frane_mesa_26318_a810_smart_gmem.h.26322').read_text()
turbo = Path('/tmp/frane_mesa_26320_a810_gmem_turbo.h.26322').read_text()
reference = smart[smart.index('static inline'):smart.rindex('#endif')]
reference += turbo[turbo.index('static inline'):turbo.rindex('#endif')]
for name in ['frane_26318_eval_smart_gmem', 'frane_26318_decide_smart_gmem',
             'frane_26320_decide_gmem_turbo']:
    reference = reference.replace(name, name + '_reference')
device = (v / 'tu_device.cc').read_text()
start = device.index('static void\nfrane_26323_a810_cache_options')
helper = device[start:device.index('static int\ntu_device_get_cache_uuid', start)]
compiler = (r / 'ir3/ir3_compiler.c').read_text()
start = compiler.index('      int gap = debug_get_num_option("TU_A810_26310_UBO_GAP"')
compiler_body = compiler[start:compiler.index('\n   }', start)]
disk = (r / 'ir3/ir3_disk_cache.cpp').read_text()
start = disk.index('      const uint32_t options[] = {')
disk_array = disk[start:disk.index('      static const char schema', start)]
assert set(re.findall(r'"(TU_A810_[A-Z0-9_]+)"', compiler_body)) <= set(
    re.findall(r'"(TU_A810_[A-Z0-9_]+)"', helper))
assert 'frane_2635_is_a810_chip(device->dev_id.chip_id)' in device
assert 'frane_chip == UINT64_C(0xffff44010000)' in disk

pre = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <random>
#include <string>
#define MIN2(a,b) std::min(a,b)
#define MAX2(a,b) std::max(a,b)
std::map<std::string,int64_t> env;
int64_t debug_get_num_option(const char *n,int64_t d) {auto i=env.find(n);return i==env.end()?d:i->second;}
bool debug_get_bool_option(const char *n,bool d) {return debug_get_num_option(n,d)!=0;}
struct fake_compiler {
 uint32_t frane_26310_ubo_gap;
 bool frane_26311_safe_tex_prefetch,frane_26312_dual_tex_prefetch;
 bool frane_26314_triple_tex_prefetch,frane_26315_prefetch_diversity;
 bool frane_26315_quad_tex_prefetch,frane_26316_prefetch_use_score;
 bool frane_26317_adaptive_sched;
 uint8_t frane_26317_tex_window_max;
};
'''
pre += f'#include "{v / "frane_mesa_26320_a810_gmem_turbo.h"}"\n'
pre += reference + helper
pre += 'std::array<uint32_t,9> actual_compiler_key() {fake_compiler obj{}; auto *compiler=&obj;\n'
pre += compiler_body + '\n' + disk_array
pre += 'std::array<uint32_t,9> out;std::copy(options,options+9,out.begin());return out;}\n'
main = r'''
bool equal(const frane_26318_smart_gmem_decision &a,const frane_26318_smart_gmem_decision &b){
 return a.override_mode==b.override_mode && a.select_sysmem==b.select_sysmem &&
 a.force_measure==b.force_measure && a.structure_score==b.structure_score &&
 a.probe_log2==b.probe_log2 && a.effective_sysmem_probability==b.effective_sysmem_probability;
}
void check_cache(){uint32_t key[10];frane_26323_a810_cache_options(key);auto actual=actual_compiler_key();for(int i=0;i<9;i++)assert(key[i]==actual[i]);}
int main(){
 std::mt19937_64 rng(0x26323);
 for(unsigned n=0;n<1000000;n++){
  frane_26318_smart_gmem_input in{};
  in.layout.physical_gmem=(rng()%2304)*1024;
  in.layout.usable_gmem=(rng()%2304)*1024;
  in.layout.pixels_per_tile=rng()%262145;
  in.layout.pass_pixels=rng()%2500001;
  in.layout.drawcalls=rng()%513;
  in.layout.selected_tile_count=n%2 ? rng()%34 : 0;
  in.sysmem_bandwidth_per_pixel=rng()%65;in.gmem_bandwidth_per_pixel=rng()%65;
  if(n%100==0){in.layout.pixels_per_tile=UINT64_MAX;in.layout.selected_tile_count=UINT64_MAX;}
  frane_2634_gmem_state state{uint8_t(rng()%256),bool(rng()%2)};
  uint32_t p=rng()%131;uint64_t word=rng();bool enabled=rng()%2;
  assert(equal(frane_26318_decide_smart_gmem_reference(enabled,in,state,p,word),frane_26318_decide_smart_gmem(enabled,in,state,p,word)));
  assert(equal(frane_26320_decide_gmem_turbo_reference(enabled,in,state,p,word),frane_26320_decide_gmem_turbo(enabled,in,state,p,word)));
 }
 // Exercise boundaries of strong-state policy for every probability and probe phase.
 frane_26318_smart_gmem_input in{};in.layout={576*1024,448*1024,131072,1280*720,64,9};in.sysmem_bandwidth_per_pixel=24;in.gmem_bandwidth_per_pixel=10;
 for(unsigned p=0;p<=101;p++)for(unsigned score=0;score<=9;score++)for(bool armed:{false,true})for(unsigned word=0;word<256;word++){
  frane_2634_gmem_state state{uint8_t(score),armed};
  assert(equal(frane_26320_decide_gmem_turbo_reference(true,in,state,p,word),frane_26320_decide_gmem_turbo(true,in,state,p,word)));
 }
 check_cache();uint32_t base[10];frane_26323_a810_cache_options(base);
 const char *names[]={"TU_A810_26310_UBO_GAP","TU_A810_26311_SAFE_TEX_PREFETCH","TU_A810_26312_DUAL_TEX_PREFETCH","TU_A810_26314_TRIPLE_TEX_PREFETCH","TU_A810_26315_PREFETCH_DIVERSITY","TU_A810_26315_QUAD_TEX_PREFETCH","TU_A810_26316_PREFETCH_USE_SCORE","TU_A810_26317_ADAPTIVE_SCHED","TU_A810_26317_TEX_WINDOW_MAX","TU_A810_26313_LRZ_FASTPATH"};
 for(int i=0;i<10;i++){env.clear();env[names[i]]=i==0?32:i==8?8:!base[i];check_cache();uint32_t key[10];frane_26323_a810_cache_options(key);assert(memcmp(key,base,sizeof(key))!=0);}
 for(int64_t gap:{-1LL,0LL,32LL,64LL,128LL,129LL,4294967296LL})for(int64_t window:{-1LL,0LL,7LL,8LL,12LL,16LL,17LL,4294967296LL})for(unsigned bits=0;bits<128;bits++){
  env.clear();env[names[0]]=gap;env[names[8]]=window;
  for(int i=1;i<=7;i++)env[names[i]]=(bits>>(i-1))&1;
  check_cache();
 }
 env.clear();env[names[0]]=123;uint32_t normalized[10];frane_26323_a810_cache_options(normalized);assert(memcmp(normalized,base,sizeof(base))==0);
 puts("PASS: 1,522,240 TURBO decisions + 1,000,000 SMART decisions equivalent; all 10 cache settings discriminate; 6,272 normalization combinations match actual compiler fields.");
}
'''
with tempfile.TemporaryDirectory() as d:
    p = Path(d) / 'audit.cpp'
    p.write_text(pre + main)
    exe = Path(d) / 'audit'
    subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined',str(p),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,env={**os.environ,
       'ASAN_OPTIONS':os.environ.get('ASAN_OPTIONS','detect_leaks=1:halt_on_error=1'),
       'UBSAN_OPTIONS':'halt_on_error=1'})
