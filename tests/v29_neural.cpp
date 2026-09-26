#include "../patches/frane_v29_neural.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>
using namespace frane_v29;
float predict(const network &n, const features &x) {
 std::array<float,network::H>a{};std::array<float,network::J>b{};
 return n.forward(x,a,b);
}
int main() {
 network n;features x{.2f,.7f,.5f,.3f,.8f,.4f,.6f,.9f};
 assert(n.valid() && n.hint(x)==50 && sizeof(n)<1024);
 // Check backprop through ALL layers against numerical loss gradients.
 network stepped=n; stepped.train(x,.4f);
 for(unsigned i=0;i<network::N;i++) {
  network hi=n,lo=n; hi.w[i]+=.001f; lo.w[i]-=.001f;
  float a=predict(hi,x)-.4f,b=predict(lo,x)-.4f;
  float numerical=(a*a-b*b)/.004f;
  float actual=(n.w[i]-stepped.w[i])/.02f;
  assert(std::abs(numerical-actual)<.0003f);
 }
 features left{.1f,.3f,.5f,.2f,.1f,.8f,.4f,.1f};
 features right{.9f,.3f,.5f,.2f,.8f,.1f,.4f,.9f};
 for(unsigned i=0;i<12000;i++) { n.train(left,-.5f);n.train(right,.5f); }
 assert(n.valid());assert(n.hint(left)==40 && n.hint(right)==60);
 assert(predict(n,left)<-.4f && predict(n,right)>.4f);
 // A changing workload must be able to reverse previously learned preference.
 for(unsigned i=0;i<12000;i++) { n.train(left,.5f);n.train(right,-.5f); }
 assert(n.hint(left)==60 && n.hint(right)==40);
 network restored;std::memcpy(&restored,&n,sizeof(n));
 assert(restored.valid() && restored.hint(left)==n.hint(left));
 restored.w[3]=std::numeric_limits<float>::quiet_NaN();assert(!restored.valid());
 restored=n;restored.version=99;assert(!restored.valid());
 restored=n;restored.w[2]=3;assert(!restored.valid());
 auto old=n.count;x[0]=std::numeric_limits<float>::infinity();n.train(x,0);
 assert(n.count==old && n.hint(x)==50);
 // Stateless counter hashing distributes decisions without shared RNG state.
 unsigned sys=0;for(uint64_t i=0;i<100000;i++)sys+=(mix(i*UINT64_C(0x9e3779b97f4a7c15))%100)<50;
 assert(sys>49000 && sys<51000);
 std::cout<<"V29 gradient, online learning, reversal, cache corruption, bounds and decision distribution PASS; model="<<sizeof(n)<<" bytes\n";
}
