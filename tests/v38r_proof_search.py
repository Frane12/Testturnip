#!/usr/bin/env python3
"""Model and proof-safety checks for A810 V38R PROOF-SEARCH."""

import random
from pathlib import Path

CPPS = (1, 2, 4, 8, 16)
MAX_ITEMS = 12
V38_BUDGET = 1024
MEMO_SLOTS = 64
MEMO_PROBES = 4

def mask(first, last):
    return ((1 << (last - first + 1)) - 1) << first

def blocks_for_pixels(pixels_count, cpp, align=4096, shift=3):
    gran = max(1, cpp >> shift)
    n = (pixels_count * cpp + align - 1) // align
    n = max(n, gran)
    return (n + gran - 1) & ~(gran - 1)

def capacity(tracks, total_blocks, align=4096, shift=3):
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

def global_upper(items, total_blocks):
    subpasses = sorted(
        {sp for _, first, last in items for sp in range(first, last + 1)}
    )
    upper = (1 << 31) - 1
    for subpass in subpasses:
        active = [
            [cpp, 0]
            for cpp, first, last in items
            if first <= subpass <= last
        ]
        if active:
            upper = min(upper, capacity(active, total_blocks))
    return upper

def future_upper(items, pos, tracks, total_blocks):
    if pos >= len(items):
        return capacity(tracks, total_blocks)

    upper = capacity(tracks, total_blocks) if tracks else (1 << 31) - 1
    subpasses = sorted(
        {sp for _, first, last in items[pos:] for sp in range(first, last + 1)}
    )

    for subpass in subpasses:
        active = sorted(
            [
                cpp
                for cpp, first, last in items[pos:]
                if first <= subpass <= last
            ],
            reverse=True,
        )
        free = sorted(
            [cpp for cpp, busy in tracks if not (busy & (1 << subpass))]
        )
        pressure = [t[:] for t in tracks]

        for cpp in active:
            match = next(
                (i for i, free_cpp in enumerate(free) if free_cpp >= cpp),
                None,
            )
            if match is None:
                pressure.append([cpp, 0])
            else:
                free.pop(match)

        upper = min(upper, capacity(pressure, total_blocks))

    return upper

def adaptive_budget(seed, proof):
    if proof <= seed:
        return 0
    if seed == 0:
        return 2048
    delta = proof - seed
    if delta * 100 <= seed:
        return 128
    if delta * 100 <= seed * 3:
        return 256
    if delta * 100 <= seed * 6:
        return 512
    if delta * 100 <= seed * 12:
        return 1024
    return 2048

def fnv_mix(h, value):
    h ^= value & ((1 << 64) - 1)
    return (h * 1099511628211) & ((1 << 64) - 1)

class Memo:
    def __init__(self):
        self.slots = [None] * MEMO_SLOTS
        self.hits = 0

    def seen(self, pos, tracks):
        if not tracks:
            return False

        canonical = tuple(sorted((cpp, busy) for cpp, busy in tracks))
        h = 1469598103934665603
        h = fnv_mix(h, pos)
        h = fnv_mix(h, len(canonical))
        for cpp, busy in canonical:
            h = fnv_mix(h, cpp)
            h = fnv_mix(h, busy)

        base = h & (MEMO_SLOTS - 1)
        state = (pos, canonical)

        for probe in range(MEMO_PROBES):
            slot = (base + probe) & (MEMO_SLOTS - 1)
            current = self.slots[slot]
            if current is None:
                self.slots[slot] = state
                return False
            if current == state:
                self.hits += 1
                return True

        self.slots[base] = state
        return False

def search(items, total_blocks, *, v38r):
    seed_tracks, sorted_items = v37(items)
    seed = capacity(seed_tracks, total_blocks)

    if len(sorted_items) > MAX_ITEMS:
        return seed, seed, 0, 0

    if v38r:
        proof = global_upper(sorted_items, total_blocks)
        if proof <= seed:
            return seed, seed, 0, 0
        budget = adaptive_budget(seed, proof)
        memo = Memo()
    else:
        budget = V38_BUDGET
        memo = None

    best = seed
    nodes = 0

    def recurse(pos, tracks):
        nonlocal best, nodes
        if nodes >= budget:
            return
        nodes += 1

        if v38r and memo.seen(pos, tracks):
            return

        if v38r:
            upper = future_upper(sorted_items, pos, tracks, total_blocks)
            if upper <= best:
                return
        elif tracks and capacity(tracks, total_blocks) <= best:
            return

        if pos == len(sorted_items):
            best = max(best, capacity(tracks, total_blocks))
            return

        cpp, first, last = sorted_items[pos]
        m = mask(first, last)

        options = []
        local_seen = set()
        for i, (tcpp, busy) in enumerate(tracks):
            if busy & m or tcpp < cpp:
                continue
            sig = (tcpp, busy)
            if sig in local_seen:
                continue
            local_seen.add(sig)
            options.append((tcpp - cpp, -busy.bit_count(), i))

        options.sort()

        for _, __, track in options:
            old = tracks[track][1]
            tracks[track][1] |= m
            recurse(pos + 1, tracks)
            tracks[track][1] = old
            if nodes >= budget:
                return

        if len(tracks) < MAX_ITEMS:
            tracks.append([cpp, m])
            recurse(pos + 1, tracks)
            tracks.pop()

    recurse(0, [])
    return seed, best, nodes, memo.hits if memo else 0

def exact_completion(items, pos, tracks, total_blocks):
    best = 0

    def recurse(p, current):
        nonlocal best
        if p == len(items):
            best = max(best, capacity(current, total_blocks))
            return

        cpp, first, last = items[p]
        m = mask(first, last)
        local_seen = set()

        for i, (tcpp, busy) in enumerate(current):
            if busy & m or tcpp < cpp:
                continue
            sig = (tcpp, busy)
            if sig in local_seen:
                continue
            local_seen.add(sig)
            old = current[i][1]
            current[i][1] |= m
            recurse(p + 1, current)
            current[i][1] = old

        current.append([cpp, m])
        recurse(p + 1, current)
        current.pop()

    recurse(pos, [t[:] for t in tracks])
    return best

# Known V38 counterexample must retain the strict capacity win.
fixture = [
    (8, 5, 6),
    (1, 3, 4),
    (2, 2, 3),
    (2, 4, 5),
]
a = search(fixture, 16, v38r=False)
b = search(fixture, 16, v38r=True)
assert a[:2] == (5632, 6144), a
assert b[:2] == (5632, 6144), b

# Prove the global and partial upper bounds never fall below an exhaustive
# optimum on small randomized states.
rng = random.Random(0x38A810)
for _ in range(1200):
    count = rng.randint(3, 7)
    items = []
    for __ in range(count):
        cpp = rng.choice((1, 2, 4, 8))
        first = rng.randint(0, 4)
        last = rng.randint(first, min(5, first + rng.randint(0, 2)))
        items.append((cpp, first, last))

    total_blocks = rng.choice((16, 24, 32, 48))
    seed_tracks, sorted_items = v37(items)
    exact = exact_completion(sorted_items, 0, [], total_blocks)
    assert global_upper(sorted_items, total_blocks) >= exact

    pos = rng.randint(0, count)
    tracks = []
    for i in range(pos):
        cpp, first, last = sorted_items[i]
        m = mask(first, last)
        legal = [
            j
            for j, (tcpp, busy) in enumerate(tracks)
            if not (busy & m) and tcpp >= cpp
        ]
        if legal and rng.random() < 0.7:
            tracks[rng.choice(legal)][1] |= m
        else:
            tracks.append([cpp, m])

    exact_tail = exact_completion(sorted_items, pos, tracks, total_blocks)
    assert future_upper(sorted_items, pos, tracks, total_blocks) >= exact_tail

# Broad bounded-search comparison. V38R is allowed to search less, but must not
# lose any V38 strict-win in this deterministic corpus.
rng = random.Random(0x3838A810)
checks = 50000
v38_wins = 0
v38r_wins = 0
nodes_v38 = 0
nodes_v38r = 0
memo_hits = 0

for _ in range(checks):
    count = rng.randint(3, MAX_ITEMS)
    items = []
    for __ in range(count):
        cpp = rng.choice(CPPS)
        first = rng.randint(0, 10)
        last = rng.randint(first, min(13, first + rng.randint(0, 4)))
        items.append((cpp, first, last))

    total_blocks = rng.choice((16, 24, 32, 48, 64, 96))
    old = search(items, total_blocks, v38r=False)
    new = search(items, total_blocks, v38r=True)

    assert new[1] >= old[1], (items, total_blocks, old, new)

    v38_wins += old[1] > old[0]
    v38r_wins += new[1] > new[0]
    nodes_v38 += old[2]
    nodes_v38r += new[2]
    memo_hits += new[3]

assert v38r_wins >= v38_wins
assert nodes_v38r * 2 < nodes_v38, (nodes_v38, nodes_v38r)

root = Path("mesa/src/freedreno/vulkan")
src = (root / "tu_pass.cc").read_text()
dev = (root / "tu_device.cc").read_text()

assert 'TU_FRANE_V38R_PROOF", true' in src
assert 'TU_FRANE_V38R_MEMO", true' in src
assert 'TU_FRANE_V38R_BUDGET", 0' in src
assert "FRANE_V38R_MEMO_SLOTS 64" in src
assert "frane_v38r_global_upper" in src
assert "frane_v38r_future_upper" in src
assert "frane_v38r_memo_seen" in src
assert "proof_upper <= seed_pixels" in src
assert "FRANE_26338_GMEM_SEARCH_MAX_ITEMS 12" in src
assert "Turnip A810 V38R / Mesa " in dev

print(
    "V38R PROOF-SEARCH PASS: "
    f"{checks} random passes, "
    f"V38 wins={v38_wins}, V38R wins={v38r_wins}, "
    f"avg nodes V38={nodes_v38/checks:.3f}, "
    f"V38R={nodes_v38r/checks:.3f}, memo_hits={memo_hits}"
)
