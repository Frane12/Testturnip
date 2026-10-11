/* SPDX-License-Identifier: MIT
 * Drnas-Turnip A810 S Ultimate v1.3 Neuro-Shadow
 * Online, paired GPU timestamp feedback. No render choice is changed.
 * Inference is bounded and lock-free; training uses one submit-side mutex.
 */
#ifndef FRANE_S1_NEURO_SHADOW_H
#define FRANE_S1_NEURO_SHADOW_H
#include <array>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <algorithm>

namespace frane_s1_neuro {
enum Mode : uint8_t { SYS = 0, GMEM = 1 };
struct Features {
  uint16_t signature = 0;
  std::array<int8_t,5> x{{1,0,0,0,0}};
  bool operator==(const Features &b) const {
    return signature==b.signature && x==b.x;
  }
};
struct Sample { Features feat; Mode mode=GMEM; uint64_t duration_ns=0; uint64_t serial=0; };
struct Gate { bool eligible=false, safe=false, force_measure=false, at4_override=false, runtime_override=false, depth_protected=false; };
struct Decision { bool trusted=false; Mode preferred=GMEM; int score=0; uint8_t stable_votes=0; };

static inline Features from_signature(uint16_t sig) {
  Features f{};
  f.signature=sig;
  const int tile=(sig>>3)&3, draws=(sig>>5)&3;
  const int bw=(sig>>9)&7;
  f.x={{1,int8_t(2-tile),
     int8_t(std::clamp(draws-tile,-2,2)),
     int8_t(bw<=4 ? 2-bw : 0),
     int8_t((sig&(1u<<12)) ? -1 : 1)}};
  return f;
}
static inline uint64_t pack(uint16_t signature, uint8_t votes,
                            const std::array<int8_t,5>& w) {
  uint64_t p=signature | (uint64_t(votes)<<16);
  for(unsigned i=0;i<5;i++) p|=uint64_t(uint8_t(w[i]))<<(24+8*i);
  return p;
}
static inline int signed_weight(uint64_t packed,unsigned i) {
  const uint8_t x=uint8_t((packed>>(24+8*i))&255u);
  return x<128 ? int(x) : int(x)-256;
}
static inline Decision infer_packed(uint64_t packed,const Features& f,const Gate& gate) {
  Decision d{};
  if (!f.signature || uint16_t(packed)!=f.signature || !gate.eligible || !gate.safe ||
      gate.force_measure || gate.at4_override || gate.runtime_override || gate.depth_protected)
    return d;
  const uint8_t votes=uint8_t(packed>>16);
  if (votes<3) return d;
  int score=0;
  for(unsigned i=0;i<5;i++) score+=signed_weight(packed,i)*int(f.x[i]);
  d.score=score; d.stable_votes=votes;
  d.trusted=score>=12 || score<=-12;
  d.preferred=score>=0 ? GMEM : SYS;
  return d;
}

class Bank {
  struct Pending { bool valid=false; Features feat{}; uint64_t t=0; uint64_t serial=0; };
  struct Slot {
    uint16_t signature=0;
    uint64_t last_serial=0;
    uint16_t accepted_pairs=0;
    std::array<int8_t,5> weights{};
    Pending pending[2]{};
    uint8_t stable_votes=0;
    int8_t last_label=0;
    uint64_t last_t[2]{};
  };
  std::mutex mutex_;
  Slot slots_[4]{};
  std::atomic<uint64_t> view_[4]{};
  static bool valid(const Sample& s) {
    if (!s.feat.signature || !s.duration_ns || s.duration_ns>100'000'000ull || !s.serial)
      return false;
    if (s.mode!=SYS && s.mode!=GMEM) return false;
    for(auto x:s.feat.x) if(x<-2 || x>2) return false;
    return s.feat.x[0]==1;
  }
  void publish(unsigned i) {
    Slot &s=slots_[i];
    const uint8_t confidence=s.accepted_pairs>=4 ? s.stable_votes : 0;
    view_[i].store(pack(s.signature,confidence,s.weights),std::memory_order_release);
  }
  static void update_weights(Slot& s,const Features& feat,int label) {
    int score=0;
    for(unsigned i=0;i<5;i++) score+=s.weights[i]*int(feat.x[i]);
    if(label*score>=16) return;
    for(unsigned i=0;i<5;i++)
      s.weights[i]=int8_t(std::clamp(int(s.weights[i])+3*label*int(feat.x[i]),-31,31));
  }
public:
  Bank()=default;
  Bank(const Bank&)=delete;
  Bank& operator=(const Bank&)=delete;
  Decision infer(const Features& feat,const Gate& gate) const {
    for(const auto& v:view_) {
      const auto p=v.load(std::memory_order_acquire);
      if(uint16_t(p)==feat.signature) return infer_packed(p,feat,gate);
    }
    return {};
  }
  bool train(const Sample& in) {
    if(!valid(in)) return false;
    std::lock_guard<std::mutex> lock(mutex_);
    unsigned target=4;
    for(unsigned i=0;i<4;i++)if(slots_[i].signature==in.feat.signature){target=i;break;}
    if(target==4){
      for(unsigned i=0;i<4;i++)if(!slots_[i].signature){target=i;break;}
      if(target==4){
        target=0;
        for(unsigned i=1;i<4;i++)
          if(slots_[i].last_serial<slots_[target].last_serial)target=i;
      }
      slots_[target]=Slot{};
      slots_[target].signature=in.feat.signature;
      publish(target);
    }
    Slot &s=slots_[target];
    if(in.serial<=s.last_serial)return false;
    s.last_serial=in.serial;
    const unsigned m=unsigned(in.mode);
    if(s.accepted_pairs>=4 && s.last_t[m] &&
       (in.duration_ns>2*s.last_t[m] || 2*in.duration_ns<s.last_t[m])) {
      s.stable_votes=0; s.accepted_pairs=0; s.last_label=0;
      s.pending[0]=Pending{};s.pending[1]=Pending{};
      for(auto& w:s.weights)w=int8_t(w/2);
    }
    s.last_t[m]=in.duration_ns;
    s.pending[m]=Pending{true,in.feat,in.duration_ns,in.serial};
    Pending &a=s.pending[SYS],&b=s.pending[GMEM];
    if(!a.valid||!b.valid||!(a.feat==b.feat) ||
       (a.serial>b.serial ? a.serial-b.serial : b.serial-a.serial)>64) {
      publish(target);return false;
    }
    a.valid=false;b.valid=false;
    const uint64_t sys_t=a.t,gm_t=b.t;
    const uint64_t larger=std::max(sys_t,gm_t);
    const uint64_t diff=larger-std::min(sys_t,gm_t);
    /* Avoid 64-bit multiplication overflow and noise-driven labels. */
    if(diff<=larger/13) {s.stable_votes=0;publish(target);return true;}
    const int label=gm_t<sys_t?+1:-1;
    if(s.last_label==label)s.stable_votes=uint8_t(std::min(255,int(s.stable_votes)+1));
    else {s.last_label=int8_t(label);s.stable_votes=1;}
    if(s.accepted_pairs<65535)++s.accepted_pairs;
    update_weights(s,in.feat,label);
    publish(target);
    return true;
  }
};
} // namespace frane_s1_neuro
#endif
