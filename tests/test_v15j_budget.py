#!/usr/bin/env python3
"""Exercise the actual patched budget arithmetic with minimal C++ type stubs."""
import subprocess
import tempfile
from pathlib import Path
src=Path('mesa/src/freedreno/vulkan/tu_device.cc').read_text()
start=src.index('   static const uint64_t a830_budget_percent')
end=src.index('\n}',start)
body=src[start:end]
preamble=r'''
#include <cassert>
#include <cstdint>
#include <cstdlib>
#define MIN2(a,b) ((a)<(b)?(a):(b))
#define CLAMP(x,a,b) ((x)<(a)?(a):((x)>(b)?(b):(x)))
constexpr int A8XX=8;
int64_t option;
int64_t debug_get_num_option(const char *, int64_t) { return option; }
struct Info { int chip; };
struct Physical { struct { uint64_t chip_id; } dev_id; Info *info; };
uint64_t budget(Physical *physical_device, uint64_t heap_size, uint64_t heap_used, uint64_t sys_available) {
'''
tail=r'''
}
int main(int, char **argv) {
 option=std::strtoll(argv[1],nullptr,10);
 uint64_t percent=option<30?30:(option>90?90:option);
 Info info{8}; Physical p{{0x44050001},&info};
 const uint64_t mib=1024*1024, heap=6*1024*mib, used=2*1024*mib;
 for (uint64_t free: {0ull, 1ull, 500ull*1024*1024, 2ull*1024*1024*1024}) {
   assert(budget(&p,heap,used,free)==used+free*percent/100);
   assert(budget(&p,used,used,free)==used);
 }
 for(uint64_t chip: {0x44050000ull,0xffff44050000ull}) {
   p.dev_id.chip_id=chip;
   assert(budget(&p,heap,used,1000)==used+10*percent);
 }
 p.dev_id.chip_id=0x43050a01;
 assert(budget(&p,heap,used,1000)==used+700);
 info.chip=7; assert(budget(&p,heap,used,1000)==used+900);
}
'''
with tempfile.TemporaryDirectory() as d:
    cc=Path(d)/'budget.cc'; exe=Path(d)/'budget'
    cc.write_text('#include <initializer_list>\n'+preamble+body+tail)
    subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(cc),'-o',str(exe)],check=True)
    for value in (-1,0,30,40,50,60,70,90,100):
        subprocess.run([str(exe),str(value)],check=True)
print('PASS: budget arithmetic, option clamping, heap bound, zero headroom, and non-A830 policies')
