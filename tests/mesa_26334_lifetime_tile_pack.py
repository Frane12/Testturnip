#!/usr/bin/env python3
"""Model/stress checks for 26.3.34 lifetime-aware GMEM allocation."""

import random

CPP = (1, 2, 4, 8, 16)

def free(a, first, last):
    _, af, al = a
    return af > last or al < first

def upstream(items):
    allocs = []
    assign = []
    for cpp, first, last in items:
        idx = None
        for i, a in enumerate(allocs):
            acpp, _, _ = a
            if not free(a, first, last):
                continue
            if acpp == cpp:
                idx = i
                break
            if acpp > cpp and (idx is None or allocs[idx][0] > acpp):
                idx = i
        if idx is None:
            allocs.append([cpp, first, last])
            idx = len(allocs) - 1
        else:
            allocs[idx][1] = min(allocs[idx][1], first)
            allocs[idx][2] = max(allocs[idx][2], last)
        assign.append(idx)
    return allocs, assign

def lifetime_bestfit(items):
    allocs = []
    assign = []
    for cpp, first, last in items:
        idx = None
        best = None
        span = last - first + 1
        for i, a in enumerate(allocs):
            acpp, af, al = a
            if not free(a, first, last) or acpp < cpp:
                continue
            gap = first - al - 1 if al < first else af - last - 1
            slack = acpp - cpp
            cost = gap * acpp + slack * span
            key = (cost, slack, gap, i)
            if best is None or key < best:
                best = key
                idx = i
        if idx is None:
            allocs.append([cpp, first, last])
            idx = len(allocs) - 1
        else:
            allocs[idx][1] = min(allocs[idx][1], first)
            allocs[idx][2] = max(allocs[idx][2], last)
        assign.append(idx)
    return allocs, assign

def blocks_for_pixels(pixels, cpp, align=4096, shift=3):
    gran = max(1, cpp >> shift)
    n = (pixels * cpp + align - 1) // align
    n = max(n, gran)
    return (n + gran - 1) & ~(gran - 1)

def packed_pixels(allocs, total_blocks, align=4096, shift=3):
    if not allocs:
        return 0
    cpps = [a[0] for a in allocs]

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
        greedy = min(greedy, n * align // cpp)

    lo = 0
    hi = total_blocks * align // min(cpps)
    while lo < hi:
        mid = lo + (hi - lo + 1) // 2
        need = sum(blocks_for_pixels(mid, cpp, align, shift) for cpp in cpps)
        if need <= total_blocks:
            lo = mid
        else:
            hi = mid - 1

    return max(greedy, lo)

def verify_alias_safety(items, allocs, assign):
    for n, ((cpp, first, last), idx) in enumerate(zip(items, assign)):
        assert allocs[idx][0] >= cpp
        for m in range(n):
            if assign[m] != idx:
                continue
            _, ofirst, olast = items[m]
            assert last < ofirst or olast < first, (items, n, m, idx)

# Deterministic case where lifetime scoring avoids a poor exact-cpp merge.
fixture = [
    (4, 3, 3),
    (1, 2, 3),
    (8, 1, 1),
    (1, 1, 1),
    (4, 0, 0),
    (4, 1, 2),
    (8, 2, 3),
]
u, ua = upstream(fixture)
c, ca = lifetime_bestfit(fixture)
verify_alias_safety(fixture, u, ua)
verify_alias_safety(fixture, c, ca)
assert packed_pixels(c, 16) > packed_pixels(u, 16)

# Randomized stress: candidate is only admitted on a strict packed-pixel win.
rng = random.Random(0x26334A810)
wins = 0
checks = 0
for _ in range(200000):
    count = rng.randint(2, 12)
    items = []
    for _ in range(count):
        cpp = rng.choice(CPP)
        first = rng.randint(0, 7)
        last = rng.randint(first, min(9, first + 3))
        items.append((cpp, first, last))

    u, ua = upstream(items)
    c, ca = lifetime_bestfit(items)
    verify_alias_safety(items, u, ua)
    verify_alias_safety(items, c, ca)

    for total_blocks in (16, 24, 32, 36, 48, 64, 96):
        up = packed_pixels(u, total_blocks)
        cand = packed_pixels(c, total_blocks)
        selected = cand if cand > up else up
        assert selected >= up
        wins += cand > up
        checks += 1

assert wins > 100
print(f"26.3.34 lifetime/tile model PASS: {checks} pack comparisons, {wins} strict wins")
