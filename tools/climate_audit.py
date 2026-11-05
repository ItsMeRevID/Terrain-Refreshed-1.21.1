#!/usr/bin/env python3
"""Measures how much climate volume each Terrain Refreshed cell actually keeps.

Within its own box a cell has zero climate fitness, and the finished list is scanned so that equal
fitness is won by the earlier entry. Vanilla points were carved out of these boxes, so the only
competitor that can take a cell's volume is another Terrain Refreshed cell listed before it. The
script therefore reports, for every cell, the fraction of its own box that survives the earlier
cells, alongside the per-axis spans so a degenerate lane is visible.

Usage: python tools/climate_audit.py
"""

import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = os.path.join(
    ROOT, "src", "main", "java", "net", "revskymc", "terrainrefreshed", "worldgen", "BiomeClimateTable.java"
)

AXES = 5
STEPS = 10
NAME = re.compile(r'ResourceLocation\.fromNamespaceAndPath\("terrainrefreshed",\s*"([a-z_0-9]+)"\)')
PARAM = re.compile(r"Climate\.Parameter\.(span|point)\(([^)]*)\)")


def to_box(text):
    box = []
    for match in PARAM.finditer(text):
        kind, arguments = match.group(1), match.group(2)
        numbers = [round(float(value) * 10000.0) for value in re.findall(r"-?[\d.]+", arguments)]
        if kind == "point":
            box.append((numbers[0], numbers[0]))
        else:
            box.append((numbers[0], numbers[1]))
    if len(box) != AXES:
        raise ValueError("expected %d axes, found %d: %s" % (AXES, len(box), text))
    return box


def axes(box):
    for axis in range(AXES):
        yield box[axis][0], box[axis][1]


def intersects(a, b):
    return all(not (a[i][1] < b[i][0] or b[i][1] < a[i][0]) for i in range(AXES))


def sample_lattice(box):
    """Midpoints of an even subdivision of the box, so a point never sits on an edge."""
    ranges = []
    for low, high in axes(box):
        if high == low:
            ranges.append([float(low)])
        else:
            step = (high - low) / STEPS
            ranges.append([low + step * (i + 0.5) for i in range(STEPS)])
    points = [()]
    for values in ranges:
        points = [prefix + (value,) for prefix in points for value in values]
    return points


def covered_fraction(box, blockers):
    """Share of the box taken by earlier cells, measured on the lattice."""
    if not blockers:
        return 0.0
    points = sample_lattice(box)
    taken = 0
    for point in points:
        for blocker in blockers:
            if all(point[i] >= blocker[i][0] and point[i] <= blocker[i][1] for i in range(AXES)):
                taken += 1
                break
    return float(taken) / float(len(points))


def main():
    text = open(TABLE, encoding="utf-8").read()
    cells = []
    for chunk in text.split("new Entry(")[1:]:
        cells.append((NAME.search(chunk).group(1), to_box(chunk)))
    print("cells parsed: %d" % len(cells))

    rows = []
    for index, (name, box) in enumerate(cells):
        blockers = [other for _, other in cells[:index] if intersects(box, other)]
        rows.append((1.0 - covered_fraction(box, blockers), name, len(blockers), box))

    rows.sort()

    print("\n%-24s %7s %8s  %s" % ("biome", "kept", "blockers", "axis spans (temp hum cont eros weid)"))
    for kept, name, blockers, box in rows[:25]:
        print("%-24s %6.1f%% %8d  %s" % (name, kept * 100.0, blockers,
                                         " ".join("%.4g" % ((high - low) / 10000.0) for low, high in axes(box))))

    degenerate = [(name, box) for _, name, _, box in rows if any(high == low for low, high in axes(box))]
    thin = [(name, box) for _, name, _, box in rows if min((high - low) / 10000.0 for low, high in axes(box)) < 0.05]
    print("\ncells that overlap an earlier cell at all: %d" % sum(1 for _, _, blockers, _ in rows if blockers))
    print("cells pinned on an axis (zero span): %d" % len(degenerate))
    print("cells with a span under 0.05 climate units: %d" % len(thin))
    for name, box in thin[:15]:
        print("  %-24s %s" % (name, " ".join("%.4g" % ((high - low) / 10000.0) for low, high in axes(box))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
