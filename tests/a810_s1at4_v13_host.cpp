#include "frane_a810_s1at4_coord.h"
#include <cassert>
#include <cstdio>
static frane_s1at4_result run(bool s1_mode=false, bool at4_mode=true,
   bool s1_probe=false, bool at4_probe=false, unsigned s1_score=8,
   unsigned pairs=8, unsigned score=6, bool enabled=true) {
 return frane_s1at4_coordinate(enabled,true,true,s1_mode,s1_probe,
   true,s1_score,true,at4_mode,at4_probe,true,pairs,score,2,false);
}
int main() {
 assert(run().prefer_s1);
 assert(!run(true,true).prefer_s1);
 assert(!run(false,true,true).prefer_s1);
 assert(!run(false,true,false,true).prefer_s1);
 assert(!run(false,true,false,false,6).prefer_s1);
 assert(!run(false,true,false,false,8,12).prefer_s1);
 assert(!run(false,true,false,false,8,8,10).prefer_s1);
 assert(!run(false,true,false,false,8,8,6,false).prefer_s1);
 auto c=frane_s1at4_coordinate(true,false,true,false,false,true,8,
                            true,true,false,true,8,6,2,false);
 assert(!c.prefer_s1);
 c=frane_s1at4_coordinate(true,true,true,false,false,true,8,
                            true,true,false,true,8,6,2,true);
 assert(!c.prefer_s1);
 c=frane_s1at4_coordinate(true,true,true,false,false,true,8,
                            true,true,false,true,8,6,4,false);
 assert(!c.prefer_s1);
 c=frane_s1at4_coordinate(true,true,true,false,false,true,8,
                            true,true,false,false,8,6,2,false);
 assert(!c.prefer_s1);
 std::puts("A810 S1-AT4 coordinator gates and vetoes PASS");
}
