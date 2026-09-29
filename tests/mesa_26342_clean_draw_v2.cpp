#include <cassert>
#include <cstdint>

enum Dirty : uint32_t {
   VERTEX_BUFFERS = 1u << 0,
   DESC_SETS      = 1u << 1,
   SHADER_CONSTS  = 1u << 3,
   LRZ            = 1u << 4,
   VS_PARAMS      = 1u << 5,
   SUBPASS        = 1u << 7,
   TES            = 1u << 10,
   PROGRAM        = 1u << 11,
   TCS            = 1u << 17,
   DRAW_STATE     = 1u << 20,
};

static bool initiator_cmd_dirty(uint32_t dirty)
{
   return dirty & (PROGRAM | TES | TCS | DRAW_STATE);
}

static bool bandwidth_cmd_dirty(uint32_t dirty)
{
   return dirty & (PROGRAM | SUBPASS | DRAW_STATE);
}

int main()
{
   /* The main V42 target: ordinary draw churn must not rebuild either cache. */
   assert(!initiator_cmd_dirty(VS_PARAMS));
   assert(!bandwidth_cmd_dirty(VS_PARAMS));
   assert(!initiator_cmd_dirty(VERTEX_BUFFERS | DESC_SETS | SHADER_CONSTS));
   assert(!bandwidth_cmd_dirty(VERTEX_BUFFERS | DESC_SETS | SHADER_CONSTS));

   /* Real dependencies still invalidate. */
   assert(initiator_cmd_dirty(PROGRAM));
   assert(initiator_cmd_dirty(TES));
   assert(initiator_cmd_dirty(TCS));
   assert(initiator_cmd_dirty(DRAW_STATE));

   assert(bandwidth_cmd_dirty(PROGRAM));
   assert(bandwidth_cmd_dirty(SUBPASS));
   assert(bandwidth_cmd_dirty(DRAW_STATE));

   /* LRZ-only dirtiness is unrelated to both cached scalar results. */
   assert(!initiator_cmd_dirty(LRZ));
   assert(!bandwidth_cmd_dirty(LRZ));

   return 0;
}
