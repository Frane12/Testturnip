#!/usr/bin/env python3
"""Patch verified DXVK v1.10.3 memory allocator; fail if upstream differs."""
from pathlib import Path

path = Path('src/dxvk/dxvk_memory.cpp')
s = path.read_text(encoding='utf-8')
original = '''    // Reduce the chunk size on small heaps so
    // we can at least fit in 15 allocations
    while (chunkSize * 15 > heap.size)
      chunkSize >>= 1;

    return chunkSize;
'''
replacement = '''    // Reduce the chunk size on small heaps so
    // we can at least fit in 15 allocations
    while (chunkSize * 15 > heap.size)
      chunkSize >>= 1;

    // A810/Bionic opt-in: cap DXVK's Vulkan heap allocation chunk,
    // not Adreno GMEM. Smaller chunks may lower reserved RAM at the
    // cost of more vkAllocateMemory calls and fragmentation.
    // Resolve once, never parse an environment variable per allocation.
    static const VkDeviceSize a810ChunkCap = [] () -> VkDeviceSize {
      const std::string value = env::getEnvVar("DXVK_A810_CHUNK_MB");
      if (value == "16") return VkDeviceSize(16) << 20;
      if (value == "32") return VkDeviceSize(32) << 20;
      if (value == "64") return VkDeviceSize(64) << 20;
      return 0;
    }();

    if (a810ChunkCap && chunkSize > a810ChunkCap)
      chunkSize = a810ChunkCap;

    return chunkSize;
'''
assert s.count(original) == 1, 'DXVK v1.10.3 pickChunkSize changed; refusing patch'
s = s.replace(original, replacement)
original2 = '''    if (!budget)
      budget = (heap->properties.size * 4) / 5;

    return heap->stats.memoryAllocated + allocationSize > budget;
'''
replacement2 = '''    if (!budget)
      budget = (heap->properties.size * 4) / 5;

    // Optional early trim of already empty Vulkan chunks during
    // a later allocation. Never frees live resources or GMEM tiles.
    static const uint32_t a810TrimPercent = [] () -> uint32_t {
      const std::string value = env::getEnvVar("DXVK_A810_TRIM_PERCENT");
      if (value == "60") return 60;
      if (value == "70") return 70;
      if (value == "75") return 75;
      return 0;
    }();

    if (a810TrimPercent) {
      const VkDeviceSize target =
        (heap->properties.size / 100) * a810TrimPercent;
      if (target < budget)
        budget = target;
    }

    return heap->stats.memoryAllocated + allocationSize > budget;
'''
assert s.count(original2) == 1, 'DXVK v1.10.3 memory budget changed; refusing patch'
s = s.replace(original2, replacement2)
path.write_text(s, encoding='utf-8')
print('A810 memory experiment applied to DXVK 1.10.3')