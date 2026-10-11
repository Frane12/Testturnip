#include "frane_a810_pipeline_probe.h"
#include "frane_a810_v3_cold_fastpath.h"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <string>
int main() {
 const char *path="/tmp/frane_v15_pipeline_probe_test.csv";
 std::remove(path);
 assert(setenv("TU_FRANE_PIPELINE_TRACE_PATH",path,1)==0);
 for(int i=0;i<16;++i) {
    auto t=frane_pipeline_begin();
    assert(t.seq==unsigned(i+1));
    frane_pipeline_end(t,i%2?"GRAPHICS":"COMPUTE",2,0);
 }
 std::ifstream f(path);
 assert(f.good());
 std::string line;
 assert(std::getline(f,line));
 assert(line.find("thread_cpu_us")!=std::string::npos);
 assert(std::getline(f,line));
 assert(line.find(",COMPUTE,2,")!=std::string::npos);
 frane_s1at1_context_input in {};
 in.pass_pixels=1280ull*720u;
 in.estimated_tiles=8;
 in.drawcalls=200;
 in.occurrences=80;
 in.sysmem_probability=50;
 const auto cat=frane_s1at1_catalog_for(in);
 assert(cat.signature!=0);
 frane_s1at3_snapshot ss {};
 assert(frane_v3_no_possible_candidate(in,ss));
 ss.signature=cat.signature;
 ss.samples[0]=1; ss.samples[1]=4;
 assert(frane_v3_no_possible_candidate(in,ss));
 ss.samples[0]=2; ss.samples[1]=2;
 assert(!frane_v3_no_possible_candidate(in,ss));
 ss.stale[0]=true;
 assert(frane_v3_no_possible_candidate(in,ss));
 std::puts("v1.5 pipeline logging + cold-history V3 predicate PASS");
}
