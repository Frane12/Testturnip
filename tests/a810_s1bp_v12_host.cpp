#include "frane_a810_s1_bandwidth_probe.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <string>
#include <cstdlib>
int main() {
  const char *p="/tmp/a810_s1bp_v12_buffer_test.csv";
  std::remove(p);
  assert(setenv("TU_FRANE_S1BP_TRACE_PATH",p,1)==0);
  frane_s1bp_row r{};
  r.rp_hash=1234; r.pixels=1280ull*720ull; r.tiles=12;
  r.drawcalls=34; r.sys_cpp=0; r.gmem_cpp=8;
  r.s1_override=true; r.runtime_armed=true; r.runtime_score=8;
  r.final_source="AT4_OVERRIDE";
  assert(frane_s1bp_estimate(UINT64_MAX,4)==UINT64_MAX);
  assert(frane_s1bp_estimate(0,4)==0);
  assert(frane_s1bp_estimate(24,4)==96);
  auto seq=frane_s1bp_take_sample(); assert(seq==1);
  for(int i=0;i<16;i++) frane_s1bp_trace(seq+i,r);
  std::ifstream f(p);
  assert(f.good());
  std::string hdr,row;
  assert(std::getline(f,hdr)&&std::getline(f,row));
  assert(hdr.find("sys_est_known")!=std::string::npos);
  assert(row.find(",0,8,")!=std::string::npos);
  assert(row.find("AT4_OVERRIDE")!=std::string::npos);
  std::puts("A810 S1BP buffered writing, estimation and saturation PASS");
}
