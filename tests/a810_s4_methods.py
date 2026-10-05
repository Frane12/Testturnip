from pathlib import Path
import subprocess
import tempfile
import os

s=Path('mesa/src/freedreno/vulkan/tu_pass.cc').read_text()
def function(name):
    pos=s.index(name+'(')
    start=s.rfind('static ',0,pos)
    brace=s.index('{',pos)
    depth=1
    end=brace+1
    while depth:
        depth += (s[end]=='{')-(s[end]=='}')
        end+=1
    return s[start:end]+'\n'

prefix=r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <random>
#include <chrono>
#include "frane_s4_sched.h"
#define MIN2(a,b) std::min((a),(b))
#define MAX2(a,b) std::max((a),(b))
#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))
struct tu_gmem_alloc { uint32_t cpp, gmem_offset, first_subpass, last_subpass; };
struct frane_gmem_mask_item { uint32_t slot, cpp, first_subpass, last_subpass; };
'''
structs=s[s.index('#define FRANE_26338_GMEM_SEARCH_MAX_ITEMS'):s.index('static bool\nfrane_a810_gmem_search_enabled')]
functions=''.join(function(n) for n in [
    'frane_subpass_range_mask','frane_gmem_blocks_for_pixels',
    'frane_pack_gmem_exact','frane_gmem_search_pixels',
    'frane_gmem_search_future_upper','frane_s4_span','frane_s4_peak_upper',
    'frane_s4_multiseed'])
recurse=s[s.index('struct frane_gmem_search_option {'):s.index('static bool\nfrane_refine_gmem_mask_candidate')]
main=r'''
static uint32_t brute(frane_gmem_search_ctx &c, unsigned pos,
                      frane_gmem_search_track *tracks, unsigned count) {
   if(pos==c.item_count)
      return frane_gmem_search_pixels(tracks,count,c.gmem_size,c.gmem_align,c.block_align_shift);
   uint64_t mask; assert(frane_subpass_range_mask(c.items[pos].first_subpass,c.items[pos].last_subpass,&mask));
   uint32_t result=0;
   for(unsigned t=0;t<=count;t++) {
      if(t<count && (tracks[t].busy&mask)) continue;
      auto old=tracks[t];
      tracks[t].cpp=MAX2(old.cpp,c.items[pos].cpp); tracks[t].busy=old.busy|mask;
      result=MAX2(result,brute(c,pos+1,tracks,MAX2(count,t+1)));
      tracks[t]=old;
   }
   return result;
}
static void validate(const frane_gmem_search_ctx &c) {
   if(!c.best_num_tracks) return;
   uint64_t masks[16]={}; uint32_t cpps[16]={};
   for(unsigned i=0;i<c.item_count;i++) {
      const unsigned t=c.best_assignment[i]; assert(t<c.best_num_tracks);
      uint64_t m; assert(frane_subpass_range_mask(c.items[i].first_subpass,c.items[i].last_subpass,&m));
      assert(!(masks[t]&m)); masks[t]|=m; cpps[t]=MAX2(cpps[t],c.items[i].cpp);
   }
   tu_gmem_alloc a[16]={};
   for(unsigned t=0;t<c.best_num_tracks;t++) {
      assert(cpps[t]==c.best_tracks[t].cpp); assert(masks[t]==c.best_tracks[t].busy);
      a[t].cpp=cpps[t];
   }
   const uint32_t packed=frane_pack_gmem_exact(a,c.best_num_tracks,c.gmem_size,c.gmem_align,c.block_align_shift);
   assert(packed>=c.best_pixels);
   uint64_t end=0;
   for(unsigned t=0;t<c.best_num_tracks;t++) {
      assert(a[t].gmem_offset==end); assert(a[t].gmem_offset%c.gmem_align==0);
      end += uint64_t(frane_gmem_blocks_for_pixels(c.best_pixels,a[t].cpp,c.gmem_align,c.block_align_shift))*c.gmem_align;
   }
   assert(end<=c.gmem_size);
}
int main() {
   for(unsigned p=0;p<=100;p++) for(unsigned maximum=2;maximum<=8;maximum++) for(bool sfu:{false,true}) {
      unsigned w=frane_s4_window(p,maximum,sfu); assert(w>=2 && w<=maximum);
      if(p) assert(w<=frane_s4_window(p-1,maximum,sfu));
   }
   assert(frane_s4_window(0,6,false)==6); assert(frane_s4_window(70,6,false)==2);
   assert(frane_s4_score(15,2,8,64,2)>frane_s4_score(15,1,8,4,2));
   for(unsigned p=60;p<=100;p++) for(unsigned critical:{0u,256u,UINT32_MAX})
      assert(frane_s4_score(p,1,UINT32_MAX,0,2)>frane_s4_score(p,2,0,critical,2));
   std::mt19937 r(0xA81054); unsigned wins=0, bound_checks=0; uint64_t old_nodes=0,new_nodes=0;
   auto start=std::chrono::steady_clock::now();
   for(unsigned sample=0;sample<16000;sample++) {
      const unsigned n=3+r()%14;
      frane_gmem_mask_item items[16]={};
      for(unsigned i=0;i<n;i++) {
         unsigned f=r()%(sample%2?64:8), l=MIN2(63u,f+(unsigned)(r()%8));
         items[i]={i,1u<<(r()%7),f,l};
      }
      std::stable_sort(items,items+n,[](auto &a,auto &b){return a.cpp>b.cpp;});
      frane_gmem_search_track seed[16]={}; unsigned count=0;
      for(unsigned i=0;i<n;i++) {
         uint64_t m; assert(frane_subpass_range_mask(items[i].first_subpass,items[i].last_subpass,&m));
         unsigned best=count; uint32_t slack=UINT32_MAX;
         for(unsigned t=0;t<count;t++) if(!(seed[t].busy&m) && seed[t].cpp>=items[i].cpp && seed[t].cpp-items[i].cpp<slack) {
            best=t;slack=seed[t].cpp-items[i].cpp;
         }
         if(best==count) count++;
         seed[best].cpp=MAX2(seed[best].cpp,items[i].cpp); seed[best].busy|=m;
      }
      frane_gmem_search_ctx a={}; a.items=items;a.item_count=n;
      a.gmem_size=(8+r()%137)*4096;a.gmem_align=4096;a.block_align_shift=r()%5;
      a.node_budget=sample<15000?128:16384;a.future_pressure=true;a.peak_upper=UINT32_MAX;
      a.best_pixels=frane_gmem_search_pixels(seed,count,a.gmem_size,a.gmem_align,a.block_align_shift);
      auto b=a; frane_gmem_search_track tracks[16]={};
      frane_gmem_search_recurse(&a,0,tracks,0);
      b.peak_upper=frane_s4_peak_upper(&b);
      frane_s4_multiseed(&b,4,true); frane_gmem_search_recurse(&b,0,tracks,0);
      assert(b.best_pixels>=a.best_pixels); assert(b.best_pixels<=b.peak_upper);
      assert(b.nodes<=b.node_budget+1); validate(a);validate(b);
      wins+=b.best_pixels>a.best_pixels; old_nodes+=a.nodes;new_nodes+=b.nodes;
      if(sample<1000 && n<=8) {
         frane_gmem_search_track exhaustive[16]={};
         const uint32_t optimal=brute(b,0,exhaustive,0);
         assert(b.peak_upper>=optimal); assert(b.best_pixels<=optimal);bound_checks++;
      }
   }
   assert(wins>0);
   double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
   printf("PASS S4 actual code: 16000 GMEM passes, %u strict capacity wins vs same-budget S3; %u exhaustive bounds; nodes %llu -> %llu; %.2f ms host; scheduler pressure and latency checks PASS\n",wins,bound_checks,(unsigned long long)old_nodes,(unsigned long long)new_nodes,ms);
}
'''
with tempfile.TemporaryDirectory(prefix='frane-s4-') as d:
    p=Path(d)
    (p/'s4.cpp').write_text(prefix+structs+functions+recurse+main)
    sanitize=os.environ.get('FRANE_TEST_SANITIZERS','undefined')
    subprocess.run(['g++','-std=c++17','-O2','-g','-Wall','-Wextra','-Werror',
                    '-fsanitize='+sanitize,'-Ipatches',str(p/'s4.cpp'),'-o',str(p/'s4')],check=True)
    subprocess.run([str(p/'s4')],check=True,
                   env={**os.environ,'ASAN_OPTIONS':'detect_leaks=0','UBSAN_OPTIONS':'halt_on_error=1'})
