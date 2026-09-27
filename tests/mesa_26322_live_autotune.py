from pathlib import Path
import tempfile,subprocess,os
v=Path('mesa/src/freedreno/vulkan').resolve();s=(v/'tu_autotune.cc').read_text()
cls=s[s.index('   struct profiled_algo {'):s.index('   } profiled;')]+'};\n'
avg=s[s.index('template <typename T = double> class exponential_average'):s.index('struct tu_autotune::rp_history',s.index('template <typename T = double> class exponential_average'))]
pre='''#include <algorithm>
#include <atomic>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <limits>
#include <thread>
#include <vector>
#define MIN2(a,b) std::min(a,b)
#define MAX2(a,b) std::max(a,b)
#define at_log_profiled_h(...) ((void)0)
'''
for h in ['frane_mesa_26320_a810_gmem_turbo.h','frane_mesa_26319_memory_audit.h','frane_v24_fastpath.h','frane_profiled_sampling.h','frane_v29_fast.h','frane_mesa_2633_a810_profile_turbo.h']:pre+=f'#include "{v/h}"\n'
pre+='''uint64_t now_ns=1;
uint64_t os_time_get_nano(){return now_ns;}
constexpr double GPU_TICKS_PER_US=19.2;
constexpr uint32_t MIN_PROFILE_DURATION_COUNT=5;
enum class render_mode{SYSMEM,GMEM};
'''+avg+'''struct rp_history {adaptive_average<uint64_t> sysmem_rp_average,gmem_rp_average;bool frane_cache_warmed=false;uint64_t hash=123;std::atomic<uint32_t> frane_gmem_runtime_word{0},frane_interval{32};};
'''
main=r'''
void seed(rp_history &h,bool sw){for(int i=0;i<100;i++){h.sysmem_rp_average.add(sw?19200:38400);h.gmem_rp_average.add(sw?38400:19200);}}
int main(){frane_26318_smart_gmem_input in{};in.layout={576*1024,448*1024,131072,1280*720,64,9};in.sysmem_bandwidth_per_pixel=24;in.gmem_bandwidth_per_pixel=10;
for(bool sw:{false,true})for(bool live:{false,true}){profiled_algo m(123);rp_history h;seed(h,sw);now_ns=1;for(int i=0;i<80;i++){now_ns+=1000000000;m.update(h,false,live);}assert(m.probability()==(live?(sw?99u:1u):(sw?100u:0u)));int switched=-1,measured=0;frane_2634_gmem_state st{};frane_26319_gmem_freshness fresh{};h.frane_gmem_runtime_word.store(264);
for(int i=0;i<10000;i++){bool measure=true;auto mode=m.get_optimal_mode(h,&measure,true,&in,true,true,live);now_ns+=16000000;if(measure){measured++;if(mode==render_mode::SYSMEM)h.sysmem_rp_average.add(sw?38400:19200);else h.gmem_rp_average.add(sw?19200:38400);m.update(h,false,live);st=frane_26319_update_gmem(st,fresh,h.sysmem_rp_average.get(),h.gmem_rp_average.get(),h.sysmem_rp_average.count,h.gmem_rp_average.count);h.frane_gmem_runtime_word.store(frane_2634_pack_gmem_state(st));}if(switched<0&&(sw?m.probability()<=5:m.probability()>=95))switched=i;}
if(live){assert(switched>=0&&switched<4096);assert(measured>0);assert(m.probability()>=1&&m.probability()<=99);}else{assert(switched==-1&&measured==0);}printf("%s initial=%s reversal=%d measured=%d\n",live?"LIVE":"LEGACY",sw?"SYSMEM":"GMEM",switched,measured);}
for(uint32_t hash:{0u,1u,63u,64u,127u,128u,UINT32_MAX-63u,UINT32_MAX})for(bool sw:{false,true}){profiled_algo m(hash);rp_history h;seed(h,sw);for(int i=0;i<80;i++)m.update(h,false,true);h.frane_gmem_runtime_word.store(264);for(int b=0;b<4;b++){int sys=0,gm=0;for(int i=0;i<128;i++){bool measure=false;auto mode=m.get_optimal_mode(h,&measure,true,&in,true,true,true);if(measure)(mode==render_mode::SYSMEM?sys:gm)++;}assert(sys>0&&gm>0);}}
{profiled_algo m(0);rp_history h;seed(h,false);m.update(h,true,true);assert(m.probability()==0);bool measure=true;assert(m.get_optimal_mode(h,&measure,true,&in,true,true,false)==render_mode::GMEM);assert(!measure);m.update(h,false,true);assert(m.probability()==1);}
{profiled_algo m(UINT32_MAX);rp_history h;seed(h,false);for(int i=0;i<80;i++)m.update(h,false,true);h.frane_gmem_runtime_word.store(264);std::atomic<unsigned> sys{0},gm{0};std::vector<std::thread> w;for(int t=0;t<8;t++)w.emplace_back([&](){for(int i=0;i<4096;i++){bool measure=false;auto mode=m.get_optimal_mode(h,&measure,true,&in,true,true,true);if(measure)(mode==render_mode::SYSMEM?sys:gm).fetch_add(1);}});for(auto &t:w)t.join();assert(sys>=256&&gm>=256);}
puts("PASS: reversal, legacy reproduction, wrap, bounded probes, immediate transition, concurrent recording");}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'sim.cpp';p.write_text(pre+cls+main);e=Path(d)/'sim'
 subprocess.run(['g++','-std=c++17','-O2','-pthread','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p),'-o',str(e)],check=True)
 subprocess.run([str(e)],check=True,env={**os.environ,'ASAN_OPTIONS':os.environ.get('ASAN_OPTIONS','detect_leaks=1:halt_on_error=1'),'UBSAN_OPTIONS':'halt_on_error=1'})
