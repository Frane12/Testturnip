/* SPDX-License-Identifier: MIT
 * Tiny online regressor; two hidden layers, no external runtime or GPU work.
 * This is an experimental weak prior, not a replacement for GPU profiling.
 */
#ifndef FRANE_V29_NEURAL_H
#define FRANE_V29_NEURAL_H
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <type_traits>

namespace frane_v29 {
using features = std::array<float, 8>;
inline float norm(double value, double scale) { return float(value / (value + scale)); }
inline uint64_t mix(uint64_t x) {
   x = (x ^ (x >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
   x = (x ^ (x >> 27)) * UINT64_C(0x94d049bb133111eb);
   return x ^ (x >> 31);
}
struct network {
   static constexpr unsigned I = 8, H = 12, J = 8;
   static constexpr unsigned N = H*(I+1) + J*(H+1) + J+1;
   uint32_t version = 1, count = 0;
   float error = 1, baseline_error = 1;
   std::array<float, N> w{};
   network() {
      for (unsigned i = 0; i < N; ++i)
         w[i] = (float(mix(i+17) % 2001) / 1000.f - 1.f) * .18f;
   }
   static float act(float x) { return x >= 0 ? x : .1f*x; }
   static float deriv(float x) { return x >= 0 ? 1.f : .1f; }
   bool valid() const {
      if (version != 1 || !std::isfinite(error) || !std::isfinite(baseline_error) ||
          error < 0 || error > 4 || baseline_error < 0 || baseline_error > 1) return false;
      for (float v : w) if (!std::isfinite(v) || std::abs(v) > 2.f) return false;
      return true;
   }
   static bool valid_features(const features &x) {
      for (float v : x) if (!std::isfinite(v) || v < 0 || v > 1) return false;
      return true;
   }
   float forward(const features &x, std::array<float,H> &a, std::array<float,J> &b) const {
      for (unsigned h=0; h<H; ++h) {
         float v=w[h*(I+1)+I];
         for(unsigned i=0;i<I;++i) v+=w[h*(I+1)+i]*x[i];
         a[h]=act(v);
      }
      constexpr unsigned B=H*(I+1), C=B+J*(H+1);
      for(unsigned j=0;j<J;++j) {
         float v=w[B+j*(H+1)+H];
         for(unsigned h=0;h<H;++h) v+=w[B+j*(H+1)+h]*a[h];
         b[j]=act(v);
      }
      float y=w[C+J];
      for(unsigned j=0;j<J;++j) y+=w[C+j]*b[j];
      return y;
   }
   uint32_t hint(const features &x) const {
      // Online prediction error is evaluated BEFORE each training update.
      // Warmup and a relative improvement gate prevent an untrained prior.
      if (count<64 || error>=baseline_error*.8f || !valid_features(x)) return 50;
      std::array<float,H>a{}; std::array<float,J>b{};
      float y=forward(x,a,b);
      return y > .12f ? 60 : y < -.12f ? 40 : 50;
   }
   void train(const features &x, float target) {
      if (!valid_features(x) || !std::isfinite(target) || std::abs(target)>1) return;
      std::array<float,H>a{},da{}; std::array<float,J>b{},db{};
      float y=forward(x,a,b), residual=std::clamp(y-target,-1.f,1.f);
      error=.98f*error+.02f*std::min((y-target)*(y-target),4.f);
      baseline_error=.98f*baseline_error+.02f*target*target;
      constexpr unsigned B=H*(I+1), C=B+J*(H+1);
      for(unsigned j=0;j<J;++j) db[j]=residual*w[C+j]*deriv(b[j]);
      for(unsigned h=0;h<H;++h) {
         for(unsigned j=0;j<J;++j) da[h]+=db[j]*w[B+j*(H+1)+h];
         da[h]*=deriv(a[h]);
      }
      auto step=[&](unsigned k,float grad) { w[k]=std::clamp(w[k]-.02f*std::clamp(grad,-1.f,1.f),-2.f,2.f); };
      for(unsigned j=0;j<J;++j) step(C+j,residual*b[j]);
      step(C+J,residual);
      for(unsigned j=0;j<J;++j) {
         for(unsigned h=0;h<H;++h) step(B+j*(H+1)+h,db[j]*a[h]);
         step(B+j*(H+1)+H,db[j]);
      }
      for(unsigned h=0;h<H;++h) {
         for(unsigned i=0;i<I;++i) step(h*(I+1)+i,da[h]*x[i]);
         step(h*(I+1)+I,da[h]);
      }
      if(count<UINT32_MAX) ++count;
   }
};
static_assert(std::is_trivially_copyable<network>::value);
static_assert(sizeof(network) < 1024);
}
#endif
