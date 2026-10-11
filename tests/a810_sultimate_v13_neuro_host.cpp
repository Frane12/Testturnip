#include "frane_s1_neuro_shadow.h"
#include <cassert>
#include <atomic>
#include <cstdio>
#include <thread>
using namespace frane_s1_neuro;
static Features f(uint16_t sig=0x1265) {return from_signature(sig);}
static Gate allow() {return {true,true,false,false,false,false};}
static void pair(Bank& b,Features feat,uint64_t& serial,uint64_t sys,uint64_t gm) {
  assert(!b.train({feat,SYS,sys,++serial}));
  assert(b.train({feat,GMEM,gm,++serial}));
}
int main() {
  for(unsigned s=1;s<8192;s+=137) {
    auto x=f(uint16_t(s));
    assert(x.x[0]==1);
    for(auto k:x.x) assert(k>=-2&&k<=2);
  }
  Bank model;uint64_t n=0;auto x=f();
  assert(!model.infer(x,allow()).trusted);
  for(int i=0;i<5;i++)pair(model,x,n,2000000,1000000);
  auto d=model.infer(x,allow());
  assert(d.trusted&&d.preferred==GMEM);
  for(int i=0;i<7;i++)pair(model,x,n,1000000,2000000);
  d=model.infer(x,allow());assert(d.trusted&&d.preferred==SYS);
  puts("PASS convergence + unpredictable winner reversal");
  Gate gate=allow();
  gate.force_measure=true;assert(!model.infer(x,gate).trusted);
  gate=allow();gate.at4_override=true;assert(!model.infer(x,gate).trusted);
  gate=allow();gate.runtime_override=true;assert(!model.infer(x,gate).trusted);
  gate=allow();gate.depth_protected=true;assert(!model.infer(x,gate).trusted);
  gate=allow();gate.safe=false;assert(!model.infer(x,gate).trusted);
  gate=allow();gate.eligible=false;assert(!model.infer(x,gate).trusted);
  puts("PASS AT4/S1/depth/GMEM safety veto");
  auto initial=model.infer(x,allow()).preferred;
  for(int i=0;i<70;i++) assert(!model.train({x,SYS,1000000,++n}));
  assert(model.infer(x,allow()).preferred==initial);
  puts("PASS no phantom learning from single mode");
  Bank noisy;uint64_t ns=0;auto y=f(0x1266);
  for(int i=0;i<40;i++)
    pair(noisy,y,ns,1000000+(i%2)*20000,1010000-(i%2)*20000);
  assert(!noisy.infer(y,allow()).trusted);
  puts("PASS noisy/tied observations");
  Bank interleave;uint64_t is=0;
  for(int i=0;i<5;i++) {pair(interleave,x,is,2000000,1000000);pair(interleave,y,is,1000000,2000000);}
  assert(interleave.infer(x,allow()).trusted&&interleave.infer(x,allow()).preferred==GMEM);
  assert(interleave.infer(y,allow()).trusted&&interleave.infer(y,allow()).preferred==SYS);
  assert(!interleave.infer(f(0x1267),allow()).trusted);
  puts("PASS separate phase labels");
  assert(!interleave.train({x,GMEM,3000000,++is}));
  assert(!interleave.infer(x,allow()).trusted);
  puts("PASS asynchronous regime change disarms trust");
  Bank invalid;uint64_t serial=0;auto z=f(0x1270);
  assert(!invalid.train({z,SYS,100,++serial}));
  serial+=100;
  assert(!invalid.train({z,GMEM,100,++serial}));
  assert(!invalid.infer(z,allow()).trusted);
  assert(!invalid.train({z,GMEM,0,++serial}));
  assert(!invalid.train({z,GMEM,100000001,++serial}));
  assert(!invalid.train({z,GMEM,100,1}));
  puts("PASS stale samples, invalid timestamp, out of order");
  Bank concurrent;std::atomic<bool> running{true};
  std::thread reader([&]{while(running.load(std::memory_order_relaxed)){auto t=concurrent.infer(x,allow());assert(t.score>-310&&t.score<310);}});
  uint64_t cs=0;for(int i=0;i<750;i++)pair(concurrent,x,cs,2000000,1000000);
  running.store(false);reader.join();
  puts("PASS concurrent render reads / GPU callback publishes");
  puts("ALL S1 NEURO V1.3 HOST TESTS PASS");
}
