#!/usr/bin/env python3
"""Model/stress checks for 26.3.39 future-aware GMEM pressure bound."""

import random
from pathlib import Path

CPPS = (1, 2, 4, 8, 16)
V38_MAX = 12
V39_MAX = 16
V38_BUDGET = 1024
V39_BUDGET = 4096

def mask(first, last):
    return ((1 << (last - first + 1)) - 1) << first

def blocks_for_pixels(pixels, cpp, align=4096, shift=3):
    gran = max(1, cpp >> shift)
    n = (pixels * cpp + align - 1) // align
    n = max(n, gran)
    return (n + gran - 1) & ~(gran - 1)

def pixels(tracks, total_blocks, align=4096, shift=3):
    if not tracks:
        return 0
    cpps = [t[0] for t in tracks]
    if sum(blocks_for_pixels(1, c, align, shift) for c in cpps) > total_blocks:
        return 0
    lo = 1
    hi = total_blocks * align // min(cpps)
    while lo < hi:
        mid = lo + (hi - lo + 1) // 2
        needed = sum(blocks_for_pixels(mid, c, align, shift) for c in cpps)
        if needed <= total_blocks:
            lo = mid
        else:
            hi = mid - 1
    return lo

def v37(items):
    order = sorted(
        range(len(items)),
        key=lambda i: (
            -items[i][0],
            -(items[i][2] - items[i][1] + 1),
            items[i][1],
            i,
        ),
    )
    tracks = []
    for idx in order:
        cpp, first, last = items[idx]
        m = mask(first, last)
        best = None
        best_key = None
        for i, (tcpp, busy) in enumerate(tracks):
            if busy & m or tcpp < cpp:
                continue
            key = (tcpp - cpp, -busy.bit_count(), i)
            if best_key is None or key < best_key:
                best = i
                best_key = key
        if best is None:
            tracks.append([cpp, m])
        else:
            tracks[best][1] |= m
    return tracks, [items[i] for i in order]

def future_upper(items, pos, tracks, total_blocks):
    if pos >= len(items):
        return pixels(tracks, total_blocks)

    upper = pixels(tracks, total_blocks) if tracks else (1 << 31) - 1

    subpasses = set()
    for _, first, last in items[pos:]:
        subpasses.update(range(first, last + 1))

    for subpass in subpasses:
        active = sorted(
            [cpp for cpp, first, last in items[pos:] if first <= subpass <= last],
            reverse=True,
        )
        free = sorted(
            [cpp for cpp, busy in tracks if not (busy & (1 << subpass))]
        )

        unmatched = []
        for cpp in active:
            match = next((i for i, free_cpp in enumerate(free) if free_cpp >= cpp), None)
            if match is None:
                unmatched.append(cpp)
            else:
                free.pop(match)

        pressure = [t[:] for t in tracks] + [[cpp, 0] for cpp in unmatched]
        upper = min(upper, pixels(pressure, total_blocks))

    return upper

def search(items, total_blocks, max_items, budget, pressure):
    seed, sorted_items = v37(items)
    seed_pixels = pixels(seed, total_blocks)

    if len(sorted_items) > max_items:
        return seed_pixels, seed_pixels, 0

    best_pixels = seed_pixels
    nodes = 0

    def recurse(pos, tracks):
        nonlocal best_pixels, nodes
        nodes += 1
        if nodes > budget:
            return

        if pressure:
            upper = future_upper(sorted_items, pos, tracks, total_blocks)
            if upper <= best_pixels:
                return
        elif tracks and pixels(tracks, total_blocks) <= best_pixels:
            return

        if pos == len(sorted_items):
            best_pixels = max(best_pixels, pixels(tracks, total_blocks))
            return

        cpp, first, last = sorted_items[pos]
        m = mask(first, last)

        options = []
        seen = set()
        for i, (tcpp, busy) in enumerate(tracks):
            if busy & m or tcpp < cpp:
                continue
            sig = (tcpp, busy)
            if sig in seen:
                continue
            seen.add(sig)
            options.append((tcpp - cpp, -busy.bit_count(), i))

        options.sort()
        for _, __, track in options:
            old = tracks[track][1]
            tracks[track][1] |= m
            recurse(pos + 1, tracks)
            tracks[track][1] = old
            if nodes >= budget:
                return

        if len(tracks) < max_items:
            tracks.append([cpp, m])
            recurse(pos + 1, tracks)
            tracks.pop()

    recurse(0, [])
    return seed_pixels, best_pixels, nodes

# Existing V38 four-item counterexample must still improve identically.
fixture_v38 = [
    (8, 5, 6),
    (1, 3, 4),
    (2, 2, 3),
    (2, 4, 5),
]
v38 = search(fixture_v38, 16, V38_MAX, V38_BUDGET, False)
v39 = search(fixture_v38, 16, V39_MAX, V39_BUDGET, True)
assert v38[0] == 5632 and v38[1] == 6144, v38
assert v39[0] == 5632 and v39[1] == 6144, v39
assert v39[2] <= v38[2], (v38, v39)

# A 14-item pass outside V38's search limit where V39 finds a strict win.
fixture_v39 = [
    (1, 2, 2),
    (2, 4, 4),
    (16, 5, 6),
    (8, 9, 9),
    (4, 7, 7),
    (1, 6, 8),
    (4, 8, 9),
    (16, 10, 11),
    (2, 10, 11),
    (2, 7, 7),
    (1, 5, 8),
    (2, 5, 6),
    (2, 2, 3),
    (8, 10, 11),
]
v38_large = search(fixture_v39, 96, V38_MAX, V38_BUDGET, False)
v39_large = search(fixture_v39, 96, V39_MAX, V39_BUDGET, True)
assert v38_large[0] == v38_large[1]
assert v39_large[1] > v39_large[0], v39_large

# Validate that the future bound never underestimates the real best completion
# on small random states by comparing against an exhaustive completion search.
def exact_completion(items, pos, tracks, total_blocks):
    best = 0

    def recurse(p, current):
        nonlocal best
        if p == len(items):
            best = max(best, pixels(current, total_blocks))
            return

        cpp, first, last = items[p]
        m = mask(first, last)
        seen = set()

        for i, (tcpp, busy) in enumerate(current):
            if busy & m or tcpp < cpp:
                continue
            sig = (tcpp, busy)
            if sig in seen:
                continue
            seen.add(sig)
            old = current[i][1]
            current[i][1] |= m
            recurse(p + 1, current)
            current[i][1] = old

        current.append([cpp, m])
        recurse(p + 1, current)
        current.pop()

    recurse(pos, [t[:] for t in tracks])
    return best

rng = random.Random(0x26339A810)
for _ in range(400):
    count = rng.randint(3, 7)
    items = []
    for _ in range(count):
        cpp = rng.choice((1, 2, 4, 8))
        first = rng.randint(0, 4)
        last = rng.randint(first, min(5, first + rng.randint(0, 2)))
        items.append((cpp, first, last))

    _, sorted_items = v37(items)
    pos = rng.randint(0, count)
    tracks = []

    for i in range(pos):
        cpp, first, last = sorted_items[i]
        m = mask(first, last)
        legal = [
            j for j, (tcpp, busy) in enumerate(tracks)
            if not (busy & m) and tcpp >= cpp
        ]
        if legal and rng.random() < 0.7:
            tracks[rng.choice(legal)][1] |= m
        else:
            tracks.append([cpp, m])

    total_blocks = rng.choice((16, 24, 32, 48))
    upper = future_upper(sorted_items, pos, tracks, total_blocks)
    exact = exact_completion(sorted_items, pos, tracks, total_blocks)
    assert upper >= exact, (sorted_items, pos, tracks, upper, exact)

# Broader randomized comparison: V39 must never regress V38's best capacity
# for <=12 items, and the expanded 13..16 range must produce real extra wins.
rng = random.Random(0x39A810)
checks = 20000
v38_wins = 0
v39_wins = 0
extra_large_wins = 0
nodes_v38 = 0
nodes_v39 = 0

for _ in range(checks):
    count = rng.randint(3, V39_MAX)
    items = []
    for _ in range(count):
        cpp = rng.choice(CPPS)
        first = rng.randint(0, 10)
        last = rng.randint(first, min(13, first + rng.randint(0, 4)))
        items.append((cpp, first, last))

    total_blocks = rng.choice((16, 24, 32, 48, 64, 96))
    a = search(items, total_blocks, V38_MAX, V38_BUDGET, False)
    b = search(items, total_blocks, V39_MAX, V39_BUDGET, True)

    if count <= V38_MAX:
        assert b[1] >= a[1], (items, total_blocks, a, b)

    v38_wins += a[1] > a[0]
    v39_wins += b[1] > b[0]
    nodes_v38 += a[2]
    nodes_v39 += b[2]

    if count > V38_MAX and b[1] > b[0]:
        extra_large_wins += 1

assert v39_wins >= v38_wins
assert extra_large_wins > 50, extra_large_wins

root = Path("mesa/src/freedreno/vulkan")
src = (root / "tu_pass.cc").read_text()
dev = (root / "tu_device.cc").read_text()

assert 'TU_A810_26339_GMEM_PRESSURE_BOUND", true' in src
assert 'TU_A810_26339_GMEM_SEARCH_BUDGET", 4096' in src
assert "FRANE_26338_GMEM_SEARCH_MAX_ITEMS 16" in src
assert "frane_gmem_search_future_upper" in src
assert "remaining_subpasses &= remaining_subpasses - 1" in src
assert "future_pressure ? FRANE_26338_GMEM_SEARCH_MAX_ITEMS : 12u" in src
assert "TU_A810_26338_GMEM_SEARCH" in src
assert "Turnip A810 V39 / Mesa " in dev

print(
    "26.3.39 GMEM-PRESSURE PASS: "
    f"{checks} random passes, V38 wins={v38_wins}, V39 wins={v39_wins}, "
    f"13..16 item wins={extra_large_wins}, "
    f"avg nodes V38={nodes_v38/checks:.2f}, V39={nodes_v39/checks:.2f}"
)
