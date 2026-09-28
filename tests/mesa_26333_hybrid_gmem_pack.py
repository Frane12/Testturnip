#!/usr/bin/env python3
"""Model checks for 26.3.33 hybrid GMEM packing."""

from itertools import product

def greedy(cpps, total_blocks, gmem_align=16384, block_align_shift=3):
    blocks = total_blocks
    cpp_total = sum(cpps)
    pixels = (1 << 32) - 1
    out = []
    for cpp in cpps:
        align = max(1, cpp >> block_align_shift)
        n = max((blocks * cpp // cpp_total) & ~(align - 1), align)
        if n > blocks:
            return None, 0
        blocks -= n
        cpp_total -= cpp
        out.append(n)
        pixels = min(pixels, n * gmem_align // cpp)
    return out, pixels

def blocks_for_pixels(pixels, cpp, gmem_align=16384, block_align_shift=3):
    align = max(1, cpp >> block_align_shift)
    n = (pixels * cpp + gmem_align - 1) // gmem_align
    n = max(n, align)
    n = (n + align - 1) & ~(align - 1)
    return n

def balanced(cpps, total_blocks, gmem_align=16384, block_align_shift=3):
    lo = 0
    hi = total_blocks * gmem_align // min(cpps)
    while lo < hi:
        mid = lo + (hi - lo + 1) // 2
        need = sum(blocks_for_pixels(mid, c, gmem_align, block_align_shift)
                   for c in cpps)
        if need <= total_blocks:
            lo = mid
        else:
            hi = mid - 1
    ns = [blocks_for_pixels(lo, c, gmem_align, block_align_shift) for c in cpps]
    assert sum(ns) <= total_blocks
    pixels = min(n * gmem_align // c for n, c in zip(ns, cpps))
    return ns, pixels

# Mesa's own TODO example.
g_ns, g_px = greedy([1, 4], 64)
b_ns, b_px = balanced([1, 4], 64)
assert g_ns == [12, 52], g_ns
assert b_ns == [13, 51], b_ns
assert g_px == 196608, g_px
assert b_px == 208896, b_px

# Exhaustive small mixed-cpp sweep: balanced must never lose to greedy.
cpp_values = [1, 2, 4, 8, 16]
improved = 0
checked = 0
for count in range(2, 6):
    for cpps in product(cpp_values, repeat=count):
        for blocks in range(count, 97):
            g_ns, g_px = greedy(cpps, blocks, gmem_align=4096)
            if g_ns is None:
                continue
            b_ns, b_px = balanced(cpps, blocks, gmem_align=4096)
            assert sum(b_ns) <= blocks
            assert b_px >= g_px, (cpps, blocks, g_ns, g_px, b_ns, b_px)
            improved += b_px > g_px
            checked += 1

assert checked > 100000
assert improved > 1000
print(f"26.3.33 hybrid packing model PASS: {checked} layouts, {improved} improved")
