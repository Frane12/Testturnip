#!/usr/bin/env python3
"""Stress/model checks for 26.3.38 bounded GMEM track search."""

import random
from pathlib import Path

CPPS = (1, 2, 4, 8, 16)
MAX_ITEMS = 12
BUDGET = 1024

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
    assignment = [None] * len(items)

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
            best = len(tracks) - 1
        else:
            tracks[best][1] |= m
        assignment[idx] = best

    # V38 consumes V37-sorted items, not API order.
    sorted_items = [items[i] for i in order]
    return tracks, sorted_items

def verify_assignment(items, assignment):
    for i in range(len(items)):
        for j in range(i):
            if assignment[i] != assignment[j]:
                continue
            _, fi, li = items[i]
            _, fj, lj = items[j]
            assert li < fj or lj < fi

def v38_search(items, total_blocks, budget=BUDGET):
    seed, sorted_items = v37(items)
    seed_pixels = pixels(seed, total_blocks)
    best_pixels = seed_pixels
    best_tracks = None
    best_assignment = None
    current_assignment = [None] * len(sorted_items)
    nodes = 0

    def recurse(pos, tracks):
        nonlocal nodes, best_pixels, best_tracks, best_assignment
        nodes += 1
        if nodes > budget:
            return

        if tracks and pixels(tracks, total_blocks) <= best_pixels:
            return

        if pos == len(sorted_items):
            p = pixels(tracks, total_blocks)
            if p > best_pixels:
                best_pixels = p
                best_tracks = [t[:] for t in tracks]
                best_assignment = current_assignment[:]
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
            current_assignment[pos] = track
            recurse(pos + 1, tracks)
            tracks[track][1] = old
            if nodes >= budget:
                return

        if len(tracks) < MAX_ITEMS:
            tracks.append([cpp, m])
            current_assignment[pos] = len(tracks) - 1
            recurse(pos + 1, tracks)
            tracks.pop()

    recurse(0, [])

    if best_tracks is None:
        return seed_pixels, seed_pixels, nodes

    verify_assignment(sorted_items, best_assignment)
    return seed_pixels, best_pixels, nodes

# Deterministic counterexample to V37's local best-fit choice.
fixture = [
    (8, 5, 6),
    (1, 3, 4),
    (2, 2, 3),
    (2, 4, 5),
]
seed, best, nodes = v38_search(fixture, 16)
assert seed == 5632, seed
assert best == 6144, best
assert best > seed
assert nodes <= BUDGET + 1

rng = random.Random(0x26338A810)
wins = 0
checks = 0
max_gain_num = 0
max_gain_den = 1

for _ in range(20000):
    count = rng.randint(3, MAX_ITEMS)
    items = []
    for _ in range(count):
        cpp = rng.choice(CPPS)
        first = rng.randint(0, 8)
        last = rng.randint(first, min(10, first + rng.randint(0, 3)))
        items.append((cpp, first, last))

    total_blocks = rng.choice((16, 24, 32, 48, 64, 96))
    seed, best, nodes = v38_search(items, total_blocks)

    assert best >= seed
    assert nodes <= BUDGET + 1

    if best > seed:
        wins += 1
        if seed > 0 and best * max_gain_den > max_gain_num * seed:
            max_gain_num = best
            max_gain_den = seed
    checks += 1

assert wins > 50, wins

root = Path("mesa/src/freedreno/vulkan")
src = (root / "tu_pass.cc").read_text()
dev = (root / "tu_device.cc").read_text()

assert 'TU_A810_26338_GMEM_SEARCH", true' in src
assert 'TU_A810_26338_GMEM_SEARCH_BUDGET", 1024' in src
assert "FRANE_26338_GMEM_SEARCH_MAX_ITEMS 12" in src
assert "frane_gmem_search_recurse" in src
assert "frane_refine_gmem_mask_candidate" in src
assert "upper <= ctx->best_pixels" in src
assert "ctx.best_pixels <= seed_pixels" in src
assert "TU_A810_26337_GMEM_MASK_PACK" in src
assert "mask_pixels > pass->gmem_pixels[layout]" in src
assert "Turnip A810 V38 / Mesa " in dev

gain = (max_gain_num / max_gain_den) if max_gain_num else 1.0
print(
    f"26.3.38 GMEM-SEARCH PASS: {checks} random passes, "
    f"{wins} strict V37 wins, max modeled capacity ratio {gain:.3f}"
)
