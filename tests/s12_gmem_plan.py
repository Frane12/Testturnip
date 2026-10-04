#!/usr/bin/env python3
"""Compile and compare actual S1.1/S1.2 GMEM C++ helpers, not a Python model."""
from pathlib import Path
import subprocess, sys
src=Path('mesa/src/freedreno/vulkan/tu_pass.cc').read_text()
# Reconstruct the baseline directly from the retained complete patch.
subprocess.run(['git','-C','mesa','show','HEAD:src/freedreno/vulkan/tu_pass.cc'],capture_output=True,check=True)
base=Path('/tmp/s12-base')
base.mkdir(exist_ok=True)
subprocess.run(['git','-C','mesa','show','HEAD:src/freedreno/vulkan/tu_pass.cc'],stdout=(base/'tu_pass.cc').open('w'),check=True)
# The patch is applied to a temporary single-file git repo for source-faithful extraction.
import tempfile
with tempfile.TemporaryDirectory() as td:
    t=Path(td); f=t/'src/freedreno/vulkan/tu_pass.cc'; f.parent.mkdir(parents=True); f.write_text((base/'tu_pass.cc').read_text())
    patch=Path('patches/s1.1-complete.patch').read_text()
    start=patch.index('diff --git a/src/freedreno/vulkan/tu_pass.cc')
    end=patch.find('\ndiff --git ',start+1)
    pp=t/'baseline.patch';pp.write_text(patch[start:end if end!=-1 else None]+'\n')
    subprocess.run(['git','apply',str(pp)],cwd=t,check=True)
    original=f.read_text()
def extract(s):
    blocks=s[s.index('static uint32_t\nfrane_gmem_blocks_for_pixels'):s.index('static bool\nfrane_a810_lifetime_tile_pack_enabled')]
    masks=s[s.index('static bool\nfrane_subpass_range_mask'):s.index('static bool\nfrane_mask_item_before')]
    search=s[s.index('#define FRANE_26338_GMEM_SEARCH_MAX_ITEMS'):s.index('static struct tu_gmem_alloc *\ntu_gmem_alloc(')]
    # Test-only counter measures actual recurse calls, including cache avoidance.
    search=search.replace('   if (++ctx->nodes > ctx->node_budget)','   ++visits;\n   if (++ctx->nodes > ctx->node_budget)')
    return 'thread_local uint64_t visits=0;\n'+blocks+masks+search
prefix=r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <random>
#include <thread>
#include <vector>
#define MIN2(a,b) std::min((a),(b))
#define MAX2(a,b) std::max((a),(b))
#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))
struct tu_gmem_alloc { uint32_t gmem_offset,cpp,first_subpass,last_subpass; };
struct tu_physical_device { struct { uint64_t chip_id; } dev_id; };
constexpr uint32_t VK_FORMAT_D32_SFLOAT_S8_UINT=99;
struct tu_render_pass_attachment { bool gmem; uint32_t format; };
struct tu_render_pass { uint32_t attachment_count; tu_render_pass_attachment *attachments; };
struct frane_gmem_mask_item { uint32_t slot,cpp,first_subpass,last_subpass; };
bool debug_get_bool_option(const char *s,bool d) { if(!strcmp(s,"TU_FRANE_GMEM_PLAN")) return !getenv("S12_DISABLE"); if(!strcmp(s,"TU_FRANE_GMEM_PRESSURE")) return bool(getenv("S12_PRESSURE")); return d; }
int debug_get_num_option(const char*,int d) { return d; }
'''
main=r'''
struct Result {
 bool changed; uint32_t count;
 std::array<tu_gmem_alloc,16> alloc;
 std::array<uint64_t,16> busy;
 std::array<int,32> assignment;
 bool operator==(const Result&b)const {
  return changed==b.changed && count==b.count &&
   !memcmp(alloc.data(),b.alloc.data(),sizeof(alloc)) && busy==b.busy && assignment==b.assignment;
 }
};
using Refine = bool(*)(const tu_render_pass*,tu_gmem_alloc*,tu_gmem_alloc**,uint64_t*,const frane_gmem_mask_item*,uint32_t*,uint32_t,uint32_t,uint32_t);
Result run(Refine f,const std::vector<frane_gmem_mask_item>&items,uint32_t size,uint32_t align,uint32_t shift) {
 Result r{}; r.assignment.fill(-1);
 tu_render_pass_attachment at[16]{}; tu_gmem_alloc *aa[32]{};
 tu_render_pass pass{0,at};
 for(const auto &it:items){pass.attachment_count=MAX2(pass.attachment_count,it.slot/2+1);at[it.slot/2].gmem=true;if(it.slot&1)at[it.slot/2].format=VK_FORMAT_D32_SFLOAT_S8_UINT;}
 // Seed using the exact-mask V37 ordering and best-fit rule.
 for(uint32_t n=0;n<items.size();n++) {

  const auto &it=items[n]; uint64_t m;
  assert(old::frane_subpass_range_mask(it.first_subpass,it.last_subpass,&m));
  uint32_t best=UINT32_MAX,slack=UINT32_MAX;unsigned fill=0;
  for(uint32_t i=0;i<r.count;i++) {
   if((r.busy[i]&m)||r.alloc[i].cpp<it.cpp) continue;
   uint32_t s=r.alloc[i].cpp-it.cpp; unsigned pop=__builtin_popcountll(r.busy[i]);
   if(s<slack||(s==slack&&pop>fill)){best=i;slack=s;fill=pop;}
  }
  if(best==UINT32_MAX) { best=r.count++;r.alloc[best]={0,it.cpp,UINT32_MAX,0}; }
  r.busy[best]|=m;
  r.alloc[best].first_subpass=MIN2(r.alloc[best].first_subpass,it.first_subpass);
  r.alloc[best].last_subpass=MAX2(r.alloc[best].last_subpass,it.last_subpass);
  aa[it.slot]=&r.alloc[best];
 }
 r.changed=f(&pass,r.alloc.data(),aa,r.busy.data(),items.data(),&r.count,size,align,shift);
 for(uint32_t i=0;i<32;i++) if(aa[i])r.assignment[i]=int(aa[i]-r.alloc.data());
 // Check layout legality independently from both implementations.
 for(uint32_t i=0;i<items.size();i++) {
  assert(r.assignment[items[i].slot]>=0);
  const auto tr=r.assignment[items[i].slot];assert(uint32_t(tr)<r.count);
  assert(r.alloc[tr].cpp>=items[i].cpp);
  for(uint32_t j=0;j<i;j++) if(r.assignment[items[j].slot]==tr)
   assert(items[i].last_subpass<items[j].first_subpass || items[j].last_subpass<items[i].first_subpass);
 }
 return r;
}
void tests(unsigned seed,unsigned cases) {
 std::mt19937 rng(seed);
 for(unsigned c=0;c<cases;c++) {
  unsigned n=3+rng()%(getenv("S12_PRESSURE")?14:10);std::vector<frane_gmem_mask_item> items;
  for(unsigned i=0;i<n;i++){
   unsigned first=rng()%64,last=MIN2(63u,first+unsigned(rng()%5));
   items.push_back({2*i,1u<<(rng()%7),first,last});
  }
  std::stable_sort(items.begin(),items.end(),[](auto a,auto b){
   if(a.cpp!=b.cpp)return a.cpp>b.cpp;
   if(a.last_subpass-a.first_subpass!=b.last_subpass-b.first_subpass)return a.last_subpass-a.first_subpass>b.last_subpass-b.first_subpass;
   if(a.first_subpass!=b.first_subpass)return a.first_subpass<b.first_subpass;return a.slot<b.slot;
  });
  uint32_t size=(8+rng()%145)*4096,align=4096,shift=3;
  auto a=run(old::frane_refine_gmem_mask_candidate,items,size,align,shift);
  auto b=run(fast::frane_refine_gmem_mask_candidate,items,size,align,shift);
  assert(a==b);
  auto before=fast::visits;
  assert(b==run(fast::frane_refine_gmem_mask_candidate,items,size,align,shift));
  if(!getenv("S12_DISABLE"))assert(before==fast::visits);
  // Key changes must not consume a result from a different capacity/alignment.
  assert(run(old::frane_refine_gmem_mask_candidate,items,size+4096,2048,2)==run(fast::frane_refine_gmem_mask_candidate,items,size+4096,2048,2));
  if(c%7==0) { for(auto &it:items)it.slot=2*(n-1-it.slot/2);assert(run(old::frane_refine_gmem_mask_candidate,items,size,align,shift)==run(fast::frane_refine_gmem_mask_candidate,items,size,align,shift)); }
 }
 // Compare the threshold pruning against the exact capacity on boundary inputs.
 for(unsigned c=0;c<cases;c++){
  fast::frane_gmem_search_track tr[16]{};unsigned n=1+rng()%16;
  for(unsigned i=0;i<n;i++)tr[i].cpp=1u<<(rng()%7);
  fast::frane_gmem_search_ctx ctx{};ctx.gmem_size=(1+rng()%256)*4096;ctx.gmem_align=4096;ctx.block_align_shift=3;
  auto p=fast::frane_gmem_search_pixels(tr,n,ctx.gmem_size,ctx.gmem_align,ctx.block_align_shift);
  for(auto target:{0u,p,p? p-1:0u,p+1,UINT32_MAX}) {
   ctx.best_pixels=target;assert(fast::frane_gmem_search_can_improve(&ctx,tr,n)==(p>target));
  }
 }
}
int main(){
 tests(0x512810,20000);
 std::vector<std::thread> threads;
 for(unsigned i=0;i<4;i++)threads.emplace_back([i]{tests(0x8100+i,2000);});
 for(auto&t:threads)t.join();
 std::vector<frane_gmem_mask_item> fixture={{0,8,5,6},{2,2,2,3},{4,2,4,5},{6,1,3,4}};
 auto stencil=fixture;stencil[0].slot=0;stencil[1].slot=1;stencil[2].slot=2;stencil[3].slot=4;
 assert(run(old::frane_refine_gmem_mask_candidate,stencil,65536,4096,3)==run(fast::frane_refine_gmem_mask_candidate,stencil,65536,4096,3));
 constexpr unsigned loops=20000;
 auto bench=[&](Refine f){auto start=std::chrono::steady_clock::now();for(unsigned i=0;i<loops;i++)run(f,fixture,65536,4096,3);return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();};
 double oldms=bench(old::frane_refine_gmem_mask_candidate),fastms=bench(fast::frane_refine_gmem_mask_candidate);
 printf("PASS actual C++: 28000 randomized passes, cold/hit/capacity/alignment/slot remap, 140000 threshold checks, 4 independent threads; reference and optimized outputs identical.\n");
 printf("Host fixture: baseline %.3f ms vs optimized %.3f ms / %u repeated creations (CPU-only, not FPS).\n",oldms,fastms,loops);
}
'''
code=prefix+'\nnamespace old {\n'+extract(original)+'\n}\nnamespace fast {\n'+extract(src)+'\n}\n'+main
out=Path('/tmp/s12-gmem-tests.cc');out.write_text(code)
flags=['-std=c++20','-O2','-g','-pthread','-Wno-unused-function']
if '--sanitize' in sys.argv:flags+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
subprocess.run(['g++',*flags,str(out),'-o','/tmp/s12-gmem-tests'],check=True)
subprocess.run(['/tmp/s12-gmem-tests'],check=True)
