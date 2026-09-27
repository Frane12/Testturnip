#include <cassert>
#include <cstdint>

enum Bit : uint32_t {
   DEPTH_TEST = 1u << 0,
   DEPTH_WRITE = 1u << 1,
   DEPTH_BOUNDS = 1u << 2,
   DEPTH_COMPARE = 1u << 3,
   STENCIL_TEST = 1u << 4,
   STENCIL_OP = 1u << 5,
   STENCIL_WRITE_MASK = 1u << 6,
   A2C = 1u << 7,
   FEEDBACK = 1u << 8,
};

static bool legacy_dirty(uint32_t bits, bool core_dirty)
{
   return core_dirty || bits != 0;
}

static bool semantic_dirty(uint32_t bits, bool core_dirty,
                           bool depth_test_enabled,
                           bool stencil_test_enabled)
{
   if (!depth_test_enabled)
      bits &= ~(DEPTH_WRITE | DEPTH_COMPARE);

   if (!stencil_test_enabled)
      bits &= ~(STENCIL_OP | STENCIL_WRITE_MASK);

   return core_dirty || bits != 0;
}

int main()
{
   // Optimization cases: child state changes under disabled parent tests.
   assert(legacy_dirty(DEPTH_COMPARE, false));
   assert(!semantic_dirty(DEPTH_COMPARE, false, false, false));
   assert(!semantic_dirty(DEPTH_WRITE, false, false, false));
   assert(!semantic_dirty(STENCIL_OP, false, true, false));
   assert(!semantic_dirty(STENCIL_WRITE_MASK, false, true, false));

   // Parent enable bits always force rebuilds.
   assert(semantic_dirty(DEPTH_TEST, false, false, false));
   assert(semantic_dirty(STENCIL_TEST, false, true, false));

   // Child changes are retained when the test is active.
   assert(semantic_dirty(DEPTH_COMPARE, false, true, false));
   assert(semantic_dirty(DEPTH_WRITE, false, true, false));
   assert(semantic_dirty(STENCIL_OP, false, true, true));
   assert(semantic_dirty(STENCIL_WRITE_MASK, false, true, true));

   // Unrelated LRZ-sensitive bits are never filtered.
   assert(semantic_dirty(DEPTH_BOUNDS, false, false, false));
   assert(semantic_dirty(A2C, false, false, false));
   assert(semantic_dirty(FEEDBACK, false, false, false));

   // Core LRZ dirty always wins.
   assert(semantic_dirty(0, true, false, false));
   return 0;
}
