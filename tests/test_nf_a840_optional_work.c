/* SPDX-License-Identifier: MIT */
#include "nf_a840_optional_work.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>

static void test_no_wait_and_budget(void)
{
   struct nf_a840_optional_gate g;
   nf_a840_optional_init(&g, 100);
   uint64_t id = 0;
   assert(!nf_a840_optional_try_submit(&g, 1, 30, 20, &id));
   assert(g.skipped_budget == 1 && !g.pending);
   assert(nf_a840_optional_try_submit(&g, 2, 30, 100, &id));
   assert(id == 1 && g.pending);
   assert(!nf_a840_optional_try_submit(&g, 3, 10, 100, &id));
   assert(g.skipped_busy == 1);
   assert(!nf_a840_optional_complete(&g, 2, true));
   assert(g.pending);
   assert(nf_a840_optional_complete(&g, 1, true));
   assert(nf_a840_optional_try_submit(&g, 4, 10, 100, &id));
   assert(id == 2);
}

static void test_timeout_does_not_release_gpu_ownership(void)
{
   struct nf_a840_optional_gate g;
   nf_a840_optional_init(&g, 100);
   uint64_t id = 0;
   assert(nf_a840_optional_try_submit(&g, 1000, 1, 100, &id));
   assert(!nf_a840_optional_try_submit(&g, 1101, 1, 100, &id));
   assert(g.disabled && g.pending && g.timeouts == 1);
   assert(!nf_a840_optional_try_submit(&g, 2000, 1, 100, &id));
   assert(nf_a840_optional_complete(&g, id, true));
   assert(!g.pending && g.disabled);
   assert(!nf_a840_optional_try_submit(&g, 2001, 1, 100, &id));
}

static void test_fault_and_nonmonotonic(void)
{
   struct nf_a840_optional_gate g;
   uint64_t id;
   nf_a840_optional_init(&g, 100);
   assert(nf_a840_optional_try_submit(&g, 200, 1, 100, &id));
   assert(nf_a840_optional_complete(&g, id, false));
   assert(g.disabled);
   nf_a840_optional_init(&g, 100);
   assert(nf_a840_optional_try_submit(&g, 200, 1, 100, &id));
   assert(!nf_a840_optional_try_submit(&g, 199, 1, 100, &id));
   assert(g.disabled && g.pending);
}

int main(void)
{
   test_no_wait_and_budget();
   test_timeout_does_not_release_gpu_ownership();
   test_fault_and_nonmonotonic();
   puts("A840 noncritical GPU optional gate tests passed");
   return 0;
}
