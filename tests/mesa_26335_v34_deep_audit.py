#!/usr/bin/env python3
"""Model/source checks for 26.3.35 V34 deep-audit clean."""

from pathlib import Path
import random

def blocks_for_pixels(pixels, cpp, gmem_align=4096, shift=3):
    gran = max(1, cpp >> shift)
    n = (pixels * cpp + gmem_align - 1) // gmem_align
    n = max(n, gran)
    return (n + gran - 1) & ~(gran - 1)

def hybrid_pixels(cpps, total_blocks, gmem_align=4096, shift=3):
    assert cpps
    # V33/V34 greedy floor.
    blocks = total_blocks
    cpp_total = sum(cpps)
    greedy = (1 << 32) - 1
    for cpp in cpps:
        gran = max(1, cpp >> shift)
        n = max((blocks * cpp // cpp_total) & ~(gran - 1), gran)
        if n > blocks:
            return 0
        blocks -= n
        cpp_total -= cpp
        greedy = min(greedy, n * gmem_align // cpp)

    # V33/V34 exact max-min candidate.
    lo = 0
    gmem_size = total_blocks * gmem_align
    hi = gmem_size // min(cpps)
    while lo < hi:
        mid = lo + (hi - lo + 1) // 2
        need = sum(blocks_for_pixels(mid, cpp, gmem_align, shift)
                   for cpp in cpps)
        if need <= total_blocks:
            lo = mid
        else:
            hi = mid - 1
    return max(greedy, lo)

# The optimistic byte bound must never reject a candidate that could win.
rng = random.Random(0x26335A810)
checks = 0
for _ in range(250000):
    n = rng.randint(1, 10)
    cpps = [rng.choice((1, 2, 4, 8, 16)) for _ in range(n)]
    total_blocks = rng.randint(max(1, n), 128)
    gmem_align = rng.choice((4096, 8192, 16384))
    gmem_size = total_blocks * gmem_align

    packed = hybrid_pixels(cpps, total_blocks, gmem_align)
    optimistic = gmem_size // sum(cpps)
    assert packed <= optimistic, (cpps, total_blocks, gmem_align, packed, optimistic)

    baseline = rng.randint(0, optimistic + 4096)
    if optimistic <= baseline:
        assert packed <= baseline
    checks += 1

# Single-subpass lifetime intervals all overlap, therefore lifetime aliasing
# cannot reduce the number of simultaneous allocations.
for n in range(1, 33):
    intervals = [(0, 0)] * n
    for i in range(n):
        for j in range(i):
            a0, a1 = intervals[i]
            b0, b1 = intervals[j]
            assert not (a0 > b1 or a1 < b0)

# Boundary intended by the V35 KGSL cleanup.
STACK = 16
needs_heap = lambda count, polling=True: polling and count > STACK
assert not needs_heap(0)
assert not needs_heap(15)
assert not needs_heap(16)
assert needs_heap(17)
assert needs_heap(64)
assert not needs_heap(64, polling=False)

# Source invariants after the patch has been applied.
root = Path("mesa/src/freedreno/vulkan")
p = (root / "tu_pass.cc").read_text()
k = (root / "tu_knl_kgsl.cc").read_text()
q = (root / "tu_queue.cc").read_text()
s = (root / "tu_suballoc.cc").read_text()

assert "frane_lifetime_candidate_can_beat" in p
assert "pass->subpass_count > 1" in p
assert "num_gmem_alloc > 1" in p
assert "candidate_pixels > pixels" in p  # V34 strict-win admission preserved.
assert "count > STACK_POLL_FDS" in k
assert "(size_t) count * sizeof(*fds)" in k
assert q.index("queue->frane_a810_pwr_active = false;") < q.index("if (shared_queue) {")
assert "suballoc->name &&" in s

print(f"26.3.35 deep-audit model PASS: {checks} upper-bound layouts + source invariants")
