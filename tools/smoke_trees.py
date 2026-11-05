#!/usr/bin/env python3
"""Plants every Terrain Refreshed tree species on the running server and measures its silhouette.

A tree feature can place without error and still grow the wrong shape, so this probe does not stop
at "the blocks appeared". Each species is planted in the air above the force loaded area - clear of
any natural terrain that would otherwise be counted with it - and then walked upwards level by
level, counting the leaf and log blocks the game actually placed. The clone mask comes before
the mode, so the counting command is
`clone <from> <to> <dest> filtered <block> normal`, which reports how many blocks matched without
touching the tree. That makes the count a measurement rather than an edit.

Every form then has to match the signature of the real tree it is named after: a spruce cone that
carries most of its mass low, a pine that stays bare for half its height, a willow that hangs leaves
well below its crown, a tabebuya that is one clean dome on a bare shaft, an acacia flattened into a
disc, a cypress that never widens, a baobab four logs thick and a palm whose only leaves are fronds.

Usage: smoke_trees.py [host] [port] [password]
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon import Rcon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURES = os.path.join(ROOT, "src", "main", "resources", "data", "terrainrefreshed", "worldgen", "configured_feature")

BASE_Y = 140  # above every natural tree near spawn, so the profile is the planted species alone
DECK_Y = 260  # scratch area the clone counts are written into, far above the trees
CLONED = re.compile(r"cloned (\d+)")
GRID = [(x, z) for z in (-48, -24, 0) for x in (-48, -24, 0, 24, 48)]


def species():
    """The generated feature definitions, so the probe follows the data instead of repeating it."""
    found = []

    for name in sorted(os.listdir(FEATURES)):
        if not name.startswith("fancy_") or not name.endswith(".json"):
            continue

        with open(os.path.join(FEATURES, name), encoding="utf-8") as handle:
            config = json.load(handle)["config"]

        found.append({
            "id": name[:-5],
            "form": config["form"],
            "log": config["trunk"]["Name"],
            "leaf": config["leaves"]["Name"],
            "min_height": config["min_height"],
            "max_height": config["max_height"],
            "radius": config["canopy_radius"],
        })

    return found


def count(rcon, block, x, y, z, reach):
    """How many blocks of one type sit in a horizontal slice, without disturbing them."""
    answer = rcon.command(
        "clone %d %d %d %d %d %d %d %d %d filtered %s normal"
        % (x - reach, y, z - reach, x + reach, y, z + reach, x - reach, DECK_Y, z - reach, block)
    )
    found = CLONED.search(answer)

    if found is not None:
        return int(found.group(1))

    # An empty slice is reported as a failure rather than "cloned 0", which is how an
    # empty level is meant to read. Anything else is a real command error.
    if "No blocks were cloned" in answer:
        return 0

    raise RuntimeError("%s at y=%d -> %s" % (block, y, answer))


def clear(rcon, tree, x, z):
    """Empty the column the species is about to be planted in, so re-runs measure one tree."""
    reach = tree["radius"] + 3
    top = BASE_Y + tree["max_height"] + tree["radius"] + 4
    rcon.command(
        "fill %d %d %d %d %d %d minecraft:air" % (x - reach, BASE_Y - 2, z - reach, x + reach, top, z + reach)
    )


def profile(rcon, tree, x, z):
    """Leaf and log counts per level, from one below the base up past the tallest possible crown."""
    reach = tree["radius"] + 3
    levels = []

    for dy in range(-1, tree["max_height"] + tree["radius"] + 5):
        y = BASE_Y + dy
        levels.append((dy, count(rcon, tree["leaf"], x, y, z, reach), count(rcon, tree["log"], x, y, z, reach)))

    return levels


def crown(levels):
    """(lowest leaf level, highest leaf level, total leaves) of the planted tree."""
    leaf_levels = [dy for dy, leaves, logs in levels if leaves > 0]

    if not leaf_levels:
        return None, None, 0

    return min(leaf_levels), max(leaf_levels), sum(leaves for _, leaves, _ in levels)


def check(tree, levels):
    """Whether the measured silhouette still looks like the tree the form is named after."""
    low, high, total = crown(levels)
    radius = tree["radius"]

    if total < 20:
        return False, "only %d leaf blocks placed" % total

    span = high - low + 1
    counts = [leaves for _, leaves, _ in levels]
    widest = max(counts)
    mass = sum(dy * leaves for dy, leaves, _ in levels) / float(total) - low
    shaft = tree["min_height"] - 1

    if tree["form"] == "spreading":
        return span >= 5, "crown spans %d levels, leaf mass centred %.1f above its base" % (span, mass)
    if tree["form"] == "conical":
        return span >= 6 and mass < span * 0.5, "cone of %d levels, mass low at %.1f of %.1f" % (span, mass, span)
    if tree["form"] == "pine":
        return low >= 1 + shaft * 0.3, "shaft stays bare for %d levels before the first tier" % low
    if tree["form"] == "weeping":
        hanging = sum(leaves for dy, leaves, _ in levels if dy < low + span / 2)
        return span >= radius + 4 and hanging * 5 >= total, \
            "%d of %d leaves hang below the crown middle, %d levels of curtain" % (hanging, total, span)
    if tree["form"] == "floral":
        return span <= 2 * radius + 3 and low >= 3 and widest >= total * 0.18, \
            "dome of %d levels, %d widest, %d logs of bare shaft under it" % (span, widest, low)
    if tree["form"] == "umbrella":
        top_two = sum(leaves for dy, leaves, _ in levels if dy >= high - 1)
        return top_two * 5 >= total * 3 and widest >= 3 * radius, \
            "%d of %d leaves in the two flat top levels, %d wide" % (top_two, total, widest)
    if tree["form"] == "columnar":
        return widest <= (2 * radius + 1) ** 2 and span >= shaft * 0.4, \
            "column of %d levels, never more than %d blocks of leaf in one" % (span, widest)
    if tree["form"] == "baobab":
        thick = max(logs for dy, _, logs in levels if dy < low)
        return thick >= 4, "barrel trunk %d logs thick, arms carry %d leaves" % (thick, total)
    if tree["form"] == "palm":
        return span <= 6 and low >= shaft - 3, "fronds in the top %d levels only, %d blocks of bare shaft" % (span, low)

    return False, "no signature defined for form %s" % tree["form"]


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25576
    password = sys.argv[3] if len(sys.argv) > 3 else "terrainrefreshed"

    trees = species()
    if len(trees) > len(GRID):
        print("no probe positions left for %d species" % len(trees))
        return 1

    rcon = Rcon(host, port, password)
    failed = []
    try:
        for index, tree in enumerate(trees):
            x, z = GRID[index]
            clear(rcon, tree, x, z)
            answer = rcon.command("place feature terrainrefreshed:%s %d %d %d" % (tree["id"], x, BASE_Y, z)).strip()

            if "placed" not in answer.lower():
                print("%-16s %-10s FAILED to place -> %s" % (tree["id"], tree["form"], answer))
                failed.append(tree["id"])
                continue

            levels = profile(rcon, tree, x, z)
            ok, detail = check(tree, levels)
            print("%-16s %-10s %s at (%d,%d)  %s" % (tree["id"], tree["form"], "OK" if ok else "BAD", x, z, detail))

            if not ok:
                failed.append(tree["id"])
    finally:
        rcon.close()

    print("tree shapes: %d of %d species match their form" % (len(trees) - len(failed), len(trees)))

    if failed:
        print("wrong or missing shape: " + ", ".join(failed))

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
