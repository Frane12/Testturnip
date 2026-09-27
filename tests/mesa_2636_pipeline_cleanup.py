#!/usr/bin/env python3
"""Compile the actual patched lookup/early-return block with refcount mocks.
This tests ownership on COMPILE_REQUIRED, not GPU execution or code generation.
"""
from pathlib import Path
import subprocess
import tempfile

source = Path("mesa/src/freedreno/vulkan/tu_pipeline.cc").read_text()
a = source.index("   if (!executable_info) {\n      frane_2635_stage_probe_state")
b = source.index("      /* 26.3.6: full compiled-cache hits", a)
block = source[a:b]
assert source.index("   if (frane_stage_nir_enabled) {") > b
pre = '\n#include <cassert>\n#include <initializer_list>\n#include <cstdint>\n#include <cstdio>\n#include <cstring>\n#include "frane_mesa_2635_shader_pipeline.h"\n#define BLAKE3_KEY_LEN 32\n#define ARRAY_SIZE(a) (sizeof(a)/sizeof(a[0]))\n#define VK_PIPELINE_CREATE_2_RETAIN_LINK_TIME_OPTIMIZATION_INFO_BIT_EXT 1\n#define VK_PIPELINE_CREATE_2_FAIL_ON_PIPELINE_COMPILE_REQUIRED_BIT_KHR 2\n#define VK_PIPELINE_CREATION_FEEDBACK_APPLICATION_PIPELINE_CACHE_HIT_BIT 4\n#define VK_PIPELINE_COMPILE_REQUIRED 100\nusing mesa_shader_stage=int;\nconstexpr int MESA_SHADER_VERTEX=0;\nstruct Base {int refs=1;};\nstruct Shader {Base base;};\nstruct Nir {};\nstruct Device {int vk=0; void* mem_cache=nullptr;};\nstruct Builder {unsigned create_flags=2; void* cache=nullptr; Device* device;};\nShader cached;\nint hit_stage=4;\nShader* tu_pipeline_cache_lookup(void*, const void* key, size_t, bool* hit) {\n if (((const unsigned char*)key)[BLAKE3_KEY_LEN] != hit_stage) return nullptr;\n *hit=true; ++cached.base.refs; return &cached;\n}\nNir* tu_nir_cache_lookup(void*,const void*,size_t,bool*) {return nullptr;}\nvoid vk_pipeline_cache_object_unref(int*, Base* base) {assert(base->refs>1); --base->refs;}\nint probe() {\n Device dev;\n Builder obj; obj.device=&dev; Builder* builder=&obj;\n bool executable_info=false,cache_hit=false;\n struct {unsigned flags=0;} pipeline_feedback;\n unsigned char pipeline_blake3[32]={},nir_blake3[33]={};\n const void* stage_infos[5]={&dev,nullptr,nullptr,nullptr,&dev};\n void* nir[5]={}; Shader* shaders[5]={}; Nir* nir_shaders=nullptr;\n uint64_t frane_shader_cache_hit_mask=0;\n'
post = '\n      return -99; // Compile-permitted miss: outside this regression\'s scope.\n   }\n   return 0;\n}\nint main() {\n for (int stage: {0,4,-1}) {\n  hit_stage=stage; cached.base.refs=1;\n  for(int i=0;i<1000;i++) {\n   assert(probe()==VK_PIPELINE_COMPILE_REQUIRED);\n   assert(cached.base.refs==1);\n  }\n }\n std::puts("PASS: actual source lookup/early-return block balances references for first-hit, later-hit and all-miss paths");\n}\n'
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "cache_ownership.cpp"
    path.write_text(pre + block + post)
    exe = Path(tmp) / "cache_ownership"
    subprocess.run(["g++", "-std=c++17", "-O2", "-fsanitize=address,undefined",
                    "-I" + str(Path("mesa/src/freedreno/vulkan").resolve()),
                    str(path), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
