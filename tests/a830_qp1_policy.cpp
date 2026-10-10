#include "frane_a830_qp1.h"
#include <cassert>
#include <cstdio>
#include <limits>
int main() {
 assert(frane_a830_qp1_add(0, UINT64_MAX)==4096);
 assert(frane_a830_qp1_add(4096,1)==4096);
 assert(frane_a830_qp1_add(0,uint64_t(UINT32_MAX)*UINT32_MAX)==4096);
 assert(frane_a830_qp1_add(100,92)==192);
 frane_a830_qp1_input in{3,18,4,false};
 assert(frane_a830_qp1_skip_binning(in));
 assert(frane_a830_qp1_tune_small(in,1280*720,4,24));
 assert(!frane_a830_qp1_tune_small(in,1280*720,16,24));
 assert(!frane_a830_qp1_tune_small(in,128*128,4,24));
 assert(!frane_a830_qp1_tune_small(in,UINT64_MAX,4,24));
 in.blocked=true;
 assert(!frane_a830_qp1_skip_binning(in));
 assert(!frane_a830_qp1_tune_small(in,1280*720,4,24));
 in.blocked=false;in.tiles=16;in.vertices=192;
 assert(!frane_a830_qp1_skip_binning(in));
 in.vertices=96;assert(frane_a830_qp1_skip_binning(in));
 in.tiles=17;assert(!frane_a830_qp1_skip_binning(in));
 unsigned long long cases=0;
 for(unsigned draws=0;draws<=20;draws++)
 for(unsigned tiles=0;tiles<=20;tiles++)
 for(unsigned vertices=0;vertices<=4100;vertices++) {
  in={draws,vertices,tiles,false};
  if(frane_a830_qp1_skip_binning(in)) {
   assert(draws&&draws<=16&&vertices&&vertices<=192);
   assert(tiles>=3&&tiles<=16&&uint64_t(vertices)*tiles<=2048);
  }
  in.blocked=true;assert(!frane_a830_qp1_skip_binning(in));
  assert(!frane_a830_qp1_tune_small(in,1280*720,4,32));
  ++cases;
 }
 printf("QP1 geometry/traffic boundaries and blocked workloads: %llu cases PASS\n",cases);
}
