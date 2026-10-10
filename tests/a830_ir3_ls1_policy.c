#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include "../patches/frane_a830_ir3_ls1.h"

static unsigned bw1_window(unsigned p, unsigned cap)
{
   if (p < 20) return cap;
   if (p < 35) return cap < 10u ? cap : 10u;
   if (p < 50) return 8u;
   if (p < 65) return 6u;
   return 4u;
}

int main(void)
{
   assert(frane_a830_ir3_ls1_pressure_threshold(false,42) == 42);
   assert(frane_a830_ir3_ls1_pressure_threshold(true,42) == 50);
   assert(frane_a830_ir3_ls1_pressure_threshold(true,72) == 80);
   assert(frane_a830_ir3_ls1_pressure_threshold(true,80) == 80);
   assert(frane_a830_ir3_ls1_sy_window(true,19,12,12) == 12);
   assert(frane_a830_ir3_ls1_sy_window(true,20,10,12) == 12);
   assert(frane_a830_ir3_ls1_sy_window(true,34,10,12) == 12);
   assert(frane_a830_ir3_ls1_sy_window(true,35,8,12) == 10);
   assert(frane_a830_ir3_ls1_sy_window(true,49,8,12) == 10);
   assert(frane_a830_ir3_ls1_sy_window(true,50,6,12) == 6);
   assert(frane_a830_ir3_ls1_sy_window(true,65,4,12) == 4);
   assert(frane_a830_ir3_ls1_sy_window(true,20,10,8) == 10);
   /* An exact BW1 opt-out for every pressure and cap. */
   unsigned cases=0;
   for (unsigned p=0; p<=100; p++)
      for (unsigned cap=8; cap<=16; cap++) {
         const unsigned old=bw1_window(p,cap);
         assert(frane_a830_ir3_ls1_sy_window(false,p,old,cap)==old);
         const unsigned now=frane_a830_ir3_ls1_sy_window(true,p,old,cap);
         assert(now>=old && now<=cap);
         if (p>=50) assert(now==old);
         cases++;
      }
   printf("A830 IR3-LS1 pure C policy and BW1 opt-out PASS: %u cases\n",cases);
   return 0;
}
