#include <cassert>
#include <cstdint>
#include <cstdio>

enum Dirty : uint32_t {
   COMPUTE_DESC = 1u << 0,
   VERTEX_BUFFERS = 1u << 1,
   VS_PARAMS = 1u << 2,
   PROGRAM = 1u << 3,
   LRZ = 1u << 4,
   DESC_SETS = 1u << 5,
};

static bool
light_dirty_fastpath(uint32_t dirty,
                     uint32_t dynamic_draw_state_dirty,
                     bool dynamic_graphics_empty,
                     bool enabled)
{
   const uint32_t light_mask = VERTEX_BUFFERS | VS_PARAMS;
   const uint32_t graphics_dirty = dirty & ~COMPUTE_DESC;

   return enabled &&
          dynamic_draw_state_dirty == 0 &&
          dynamic_graphics_empty &&
          graphics_dirty != 0 &&
          (graphics_dirty & ~light_mask) == 0;
}

static unsigned
state_count(uint32_t dirty)
{
   const uint32_t graphics_dirty = dirty & ~COMPUTE_DESC;
   unsigned n = 0;
   if (graphics_dirty & VERTEX_BUFFERS) n++;
   if (graphics_dirty & VS_PARAMS) n++;
   return n;
}

int main()
{
   assert(light_dirty_fastpath(VS_PARAMS, 0, true, true));
   assert(light_dirty_fastpath(VERTEX_BUFFERS, 0, true, true));
   assert(light_dirty_fastpath(VS_PARAMS | VERTEX_BUFFERS, 0, true, true));

   assert(light_dirty_fastpath(VS_PARAMS | COMPUTE_DESC, 0, true, true));
   assert(light_dirty_fastpath(VERTEX_BUFFERS | COMPUTE_DESC, 0, true, true));

   assert(!light_dirty_fastpath(0, 0, true, true));
   assert(!light_dirty_fastpath(COMPUTE_DESC, 0, true, true));
   assert(!light_dirty_fastpath(VS_PARAMS | PROGRAM, 0, true, true));
   assert(!light_dirty_fastpath(VERTEX_BUFFERS | LRZ, 0, true, true));
   assert(!light_dirty_fastpath(VS_PARAMS | DESC_SETS, 0, true, true));
   assert(!light_dirty_fastpath(VS_PARAMS, 1, true, true));
   assert(!light_dirty_fastpath(VS_PARAMS, 0, false, true));
   assert(!light_dirty_fastpath(VS_PARAMS, 0, true, false));

   assert(state_count(VS_PARAMS) == 1);
   assert(state_count(VERTEX_BUFFERS) == 1);
   assert(state_count(VS_PARAMS | VERTEX_BUFFERS) == 2);
   assert(state_count(VS_PARAMS | COMPUTE_DESC) == 1);

   std::puts("V43 light-dirty draw model PASS");
   return 0;
}
