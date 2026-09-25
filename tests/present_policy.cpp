// SPDX-License-Identifier: MIT
#include "../patches/frane_present_policy.h"
#include <cassert>
#include <cstdio>
int main()
{
   assert(frane_present_parse(nullptr) == FRANE_PRESENT_MAILBOX);
   assert(frane_present_parse("auto") == FRANE_PRESENT_MAILBOX);
   assert(frane_present_parse("mailbox") == FRANE_PRESENT_MAILBOX);
   assert(frane_present_parse("fifo") == FRANE_PRESENT_FIFO);
   assert(frane_present_parse("relaxed") == FRANE_PRESENT_RELAXED);
   assert(frane_present_parse("immediate") == FRANE_PRESENT_IMMEDIATE);
   assert(frane_present_parse("off") == FRANE_PRESENT_OFF);
   assert(frane_present_parse("") == FRANE_PRESENT_OFF);
   assert(frane_present_parse("bogus") == FRANE_PRESENT_OFF);
   std::puts("PASS: A810 present choice, opt-out, and invalid fallback");
}
