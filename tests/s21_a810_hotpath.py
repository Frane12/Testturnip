#!/usr/bin/env python3
"""Model and source checks for Turnip-Drnas A810 S2.1 HOTPATH."""

import random
from pathlib import Path

MAX_ITEMS = 12
BUDGET = 1024
CPPS = (1, 2, 4, 8, 16)


def mask(first, last):
    return ((1 << (last - first + 1)) - 1) << first


def blocks_for_pixels(pixels, cpp, align=4096, shift=3):
    gran = max(1, cpp >> shift)
    n = (pixels * cpp + align - 1) // align
    n = max(n, gran)
    return (n + gran - 1) & ~(gran - 1)


def capacity(tracks, total_blocks, counter):
    counter[0] += 1
    if not tracks:
        return 0
    cpps = [x[0] for x in tracks]
    if sum(blocks_for_pixels(1, c) for c in cpps) > total_blocks:
        return 0
    lo, hi = 1, total_blocks * 4096 // min(cpps)
    while lo < hi:
        mid = lo + (hi - lo + 1) // 2
        need = sum(blocks_for_pixels(mid, c) for c in cpps)
        if need <= total_blocks:
            lo = mid
        else:
            hi = mid - 1
    return lo


def ordered(items):
    order = sorted(
        range(len(items)),
        key=lambda i: (-items[i][0], -(items[i][2] - items[i][1] + 1),
                       items[i][1], i),
    )
    return [items[i] for i in order]


def seed_tracks(items):
    tracks = []
    for cpp, first, last in items:
        m = mask(first, last)
        best = None
        best_key = None
        for i, (tcpp, busy) in enumerate(tracks):
            if busy & m or tcpp < cpp:
                continue
            key = (tcpp - cpp, -busy.bit_count(), i)
            if best_key is None or key < best_key:
                best, best_key = i, key
        if best is None:
            tracks.append([cpp, m])
        else:
            tracks[best][1] |= m
    return tracks


def search(items, total_blocks, carry):
    items = ordered(items)
    evals = [0]
    seed = seed_tracks(items)
    best = capacity(seed, total_blocks, evals)
    nodes = 0

    def rec(pos, tracks, cap=None):
        nonlocal best, nodes
        nodes += 1
        if nodes > BUDGET:
            return

        if tracks:
            upper = cap if carry else capacity(tracks, total_blocks, evals)
            if upper <= best:
                return

        if pos == len(items):
            p = cap if carry else capacity(tracks, total_blocks, evals)
            if p > best:
                best = p
            return

        cpp, first, last = items[pos]
        m = mask(first, last)
        opts = []
        seen = set()
        for i, (tcpp, busy) in enumerate(tracks):
            if busy & m or tcpp < cpp:
                continue
            sig = (tcpp, busy)
            if sig in seen:
                continue
            seen.add(sig)
            opts.append((tcpp - cpp, -busy.bit_count(), i))
        opts.sort()

        for _, __, i in opts:
            old = tracks[i][1]
            tracks[i][1] |= m
            rec(pos + 1, tracks, cap)
            tracks[i][1] = old
            if nodes >= BUDGET:
                return

        if len(tracks) < MAX_ITEMS:
            tracks.append([cpp, m])
            child = capacity(tracks, total_blocks, evals) if carry else None
            rec(pos + 1, tracks, child)
            tracks.pop()

    rec(0, [], None)
    return best, nodes, evals[0]


rng = random.Random(0x3810A810)
old_evals = 0
new_evals = 0
strict_reductions = 0
for _ in range(8000):
    count = rng.randint(3, MAX_ITEMS)
    items = []
    for _ in range(count):
        cpp = rng.choice(CPPS)
        first = rng.randint(0, 8)
        last = rng.randint(first, min(10, first + rng.randint(0, 3)))
        items.append((cpp, first, last))
    blocks = rng.choice((16, 24, 32, 48, 64, 96))

    old_best, old_nodes, oe = search(items, blocks, False)
    new_best, new_nodes, ne = search(items, blocks, True)
    assert new_best == old_best, (old_best, new_best, items, blocks)
    assert new_nodes == old_nodes, (old_nodes, new_nodes)
    old_evals += oe
    new_evals += ne
    strict_reductions += ne < oe

assert strict_reductions > 1000
assert new_evals < old_evals


MASK = 63


def mix64(x):
    x &= (1 << 64) - 1
    x ^= x >> 33
    x = (x * 0xff51afd7ed558ccd) & ((1 << 64) - 1)
    x ^= x >> 33
    x = (x * 0xc4ceb9fe1a85ec53) & ((1 << 64) - 1)
    x ^= x >> 33
    return x


def place(hashes, two):
    slots = [None] * 64
    for h in hashes:
        i0 = h & MASK
        candidates = [i0]
        if two:
            i1 = mix64(h) & MASK
            if i1 == i0:
                i1 = (i0 + 1) & MASK
            candidates.append(i1)
        for i in candidates:
            if slots[i] is None:
                slots[i] = h
                break
    return sum(x is not None for x in slots)


colliders = [((i + 1) << 6) for i in range(64)]
single = place(colliders, False)
dual = place(colliders, True)
assert single == 1
assert dual > single


root = Path("mesa")
gmem = (root / "src/freedreno/vulkan/tu_pass.cc").read_text()
autotune = (root / "src/freedreno/vulkan/tu_autotune.cc").read_text()
device = (root / "src/freedreno/vulkan/tu_device.cc").read_text()
sched = (root / "src/freedreno/ir3/ir3_sched.c").read_text()

for needle in (
    "uint32_t capacity)",
    "num_tracks > 0 && capacity <= ctx->best_pixels",
    "const uint32_t pixels = capacity;",
    "const uint32_t child_capacity =",
):
    assert needle in gmem

for needle in (
    'TU_FRANE_HOT2", true',
    "hot_candidates[2]",
    "0xff51afd7ed558ccd",
    "0xc4ceb9fe1a85ec53",
    "rp_history_handle(*cached, false)",
):
    assert needle in autotune

assert "frane_sh1_pressure_priority" in sched
assert "Turnip-Drnas A810 S2.1 / Mesa " in device

print(
    "S2.1 HOTPATH PASS: "
    f"GMEM exact-capacity evaluations {old_evals} -> {new_evals} "
    f"({100.0 * (old_evals-new_evals)/old_evals:.1f}% fewer in model); "
    f"HOT2 adversarial placements {single} -> {dual}; "
    "search result/node order preserved"
)
