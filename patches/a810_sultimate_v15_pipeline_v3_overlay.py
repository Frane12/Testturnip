#!/usr/bin/env python3
"""S Ultimate v1.5: optional pipeline creation CPU timing and guarded
V3 cold-history bypass, based on v1.4 after all existing safety patches.
"""
from pathlib import Path
import shutil
V=Path("mesa/src/freedreno/vulkan")
a=V/"tu_autotune.cc"
p=V/"tu_pipeline.cc"
d=V/"tu_device.cc"
for f in ("frane_a810_pipeline_probe.h","frane_a810_v3_cold_fastpath.h"):
    shutil.copyfile("patches/"+f,V/f)
def change(path,old,new,tag):
    s=path.read_text()
    n=s.count(old)
    if n!=1: raise SystemExit(f"V1.5 SOURCE DRIFT {tag}: {n}")
    path.write_text(s.replace(old,new,1))
    print("v1.5 PASS",tag,flush=True)

change(a,'#include "frane_a810_s1at4_coord.h"',
       '#include "frane_a810_s1at4_coord.h"\n#include "frane_a810_v3_cold_fastpath.h"',
       "guarded V3 fastpath helper")
change(a,
"""                  if (s1atu_v3_context && s1at4_context) {
""",
"""                  if (s1atu_v3_context && s1at4_context) {
                     /* Never skip V3 with valid paired GPU evidence.
                      * Cold category bookkeeping is optional and only
                      * bypassed when a GPU winner is impossible.
                      * AT4, S1, probes and post-selection safety unchanged.
                      */
                     static const bool v3_cold_fast =
                        debug_get_bool_option("TU_FRANE_V3_COLD_FASTPATH",false);
                     if (!v3_cold_fast ||
                         !frane_v3_no_possible_candidate(at1_in,snapshot)) {
""","optional cold-history short circuit")
change(a,
"""                        if (atu_v3_applied) *atu_v3_applied = true;
                     }
                  }
                  if (s1at8_context""",
"""                        if (atu_v3_applied) *atu_v3_applied = true;
                     }
                     }
                  }
                  if (s1at8_context""",
"close cold-history bypass without changing subsequent selector stages")
change(p,'#include "tu_device.h"',
       '#include "tu_device.h"\n#include "frane_a810_pipeline_probe.h"',
       "opt-in shader pipeline CPU timer")
change(p,
"""tu_CreateGraphicsPipelines(VkDevice device,
                           VkPipelineCache pipelineCache,
                           uint32_t count,
                           const VkGraphicsPipelineCreateInfo *pCreateInfos,
                           const VkAllocationCallbacks *pAllocator,
                           VkPipeline *pPipelines)
{
   MESA_TRACE_FUNC();
   VkResult final_result = VK_SUCCESS;""",
"""tu_CreateGraphicsPipelines(VkDevice device,
                           VkPipelineCache pipelineCache,
                           uint32_t count,
                           const VkGraphicsPipelineCreateInfo *pCreateInfos,
                           const VkAllocationCallbacks *pAllocator,
                           VkPipeline *pPipelines)
{
   MESA_TRACE_FUNC();
   const auto frane_pipe_stamp = frane_pipeline_begin();
   VkResult final_result = VK_SUCCESS;""",
"graphics pipeline creation wall/thread CPU start")
change(p,
"""   return final_result;
}
TU_GENX(tu_CreateGraphicsPipelines);""",
"""   frane_pipeline_end(frane_pipe_stamp,"GRAPHICS",count,int(final_result));
   return final_result;
}
TU_GENX(tu_CreateGraphicsPipelines);""",
"graphics pipeline creation sampled end")
change(p,
"""tu_CreateComputePipelines(VkDevice device,
                          VkPipelineCache pipelineCache,
                          uint32_t count,
                          const VkComputePipelineCreateInfo *pCreateInfos,
                          const VkAllocationCallbacks *pAllocator,
                          VkPipeline *pPipelines)
{
   MESA_TRACE_FUNC();
   VkResult final_result = VK_SUCCESS;""",
"""tu_CreateComputePipelines(VkDevice device,
                          VkPipelineCache pipelineCache,
                          uint32_t count,
                          const VkComputePipelineCreateInfo *pCreateInfos,
                          const VkAllocationCallbacks *pAllocator,
                          VkPipeline *pPipelines)
{
   MESA_TRACE_FUNC();
   const auto frane_pipe_stamp = frane_pipeline_begin();
   VkResult final_result = VK_SUCCESS;""",
"compute pipeline creation wall/thread CPU start")
change(p,
"""   return final_result;
}
TU_GENX(tu_CreateComputePipelines);""",
"""   frane_pipeline_end(frane_pipe_stamp,"COMPUTE",count,int(final_result));
   return final_result;
}
TU_GENX(tu_CreateComputePipelines);""",
"compute pipeline creation sampled end")
change(d,"Drnas-Turnip A810 S Ultimate v1.4 / Mesa ",
       "Drnas-Turnip A810 S Ultimate v1.5 / Mesa ",
       "Vulkan label")
change(d,'"Drnas-Turnip A810 S Ultimate v1.4" : pdevice->name',
       '"Drnas-Turnip A810 S Ultimate v1.5" : pdevice->name',
       "DXVK adapter label")
assert "frane_a810_gmem_pass_safe" in a.read_text()
assert "TU_FRANE_S1AT4_COORD" in a.read_text()
print("v1.5 patched only tu_autotune.cc, tu_pipeline.cc, tu_device.cc and two headers")
