#include <cassert>
#include <cstdint>
#include "../patches/frane_mesa_26353_a810_context_gmem.h"

static frane_26353_context_input base()
{
   frane_26353_context_input in {};
   in.eligible = true;
   in.structure_score = 70;
   in.measured_score = 7;
   in.measured_armed = true;
   in.sysmem_probability = 20;
   in.attachment_count = 3;
   in.gmem_attachment_count = 3;
   in.depth_attachment_count = 1;
   in.depth_reuse_span = 3;
   in.subpass_count = 2;
   in.drawcalls = 48;
   in.estimated_tiles = 8;
   in.sysmem_bandwidth_per_pixel = 24;
   in.gmem_bandwidth_per_pixel = 12;
   return in;
}

int main()
{
   {
      auto in = base();
      const auto e = frane_26353_eval_context(in);
      assert(e.score >= 55);
      const auto d = frane_26353_decide_context(1, in, 1);
      assert(d.override_mode && !d.select_sysmem);
      assert(d.probe_log2 == 9);
   }

   {
      auto in = base();
      in.structure_score = 35;
      in.measured_armed = false;
      in.measured_score = 0;
      in.sysmem_probability = 85;
      in.attachment_count = 8;
      in.gmem_attachment_count = 6;
      in.depth_attachment_count = 0;
      in.depth_reuse_span = 0;
      in.resolve_count = 4;
      in.drawcalls = 4;
      in.estimated_tiles = 22;
      in.sysmem_bandwidth_per_pixel = 12;
      in.gmem_bandwidth_per_pixel = 24;
      const auto e = frane_26353_eval_context(in);
      assert(e.score <= -35);
      const auto d = frane_26353_decide_context(1, in, 1);
      assert(d.override_mode && d.select_sysmem);
   }

   {
      auto in = base();
      in.structure_score = 50;
      in.measured_armed = false;
      in.measured_score = 0;
      in.sysmem_probability = 50;
      in.depth_attachment_count = 0;
      in.depth_reuse_span = 0;
      in.resolve_count = 2;
      in.drawcalls = 8;
      in.estimated_tiles = 12;
      in.sysmem_bandwidth_per_pixel = 16;
      in.gmem_bandwidth_per_pixel = 16;
      const auto d = frane_26353_decide_context(1, in, 17);
      assert(!d.override_mode);
   }

   {
      auto in = base();
      const auto no_probe = frane_26353_decide_context(1, in, 1);
      const auto probe = frane_26353_decide_context(1, in, 512);
      assert(no_probe.override_mode && !no_probe.force_measure);
      assert(probe.override_mode && probe.force_measure);
      assert(probe.select_sysmem);
   }

   {
      auto in = base();
      in.sysmem_probability = 75;
      in.measured_score = 3;
      in.structure_score = 58;
      in.depth_reuse_span = 1;
      in.resolve_count = 2;
      const auto e = frane_26353_eval_context(in);
      const auto d = frane_26353_decide_context(1, in, 123);
      assert(e.score < 30);
      assert(!d.override_mode || d.select_sysmem);
   }

   return 0;
}
