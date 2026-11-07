#!/usr/bin/env python3
"""Proves that the leaves of every Terrain Refreshed species cannot decay.

The game removes a leaf once it is seven leaf-steps away from the nearest log, unless the leaf is
marked persistent. The distance is not taken from the tree feature: on 1.21.1 the game recomputes
it on the tick after the leaves are placed, so the only trustworthy proof is the state the world
actually holds a moment later.

So this probe plants every species, waits for the game to run the update tick, and then asks the
world which leaves are in the state that decays. The count is read with
`fill <box> minecraft:air replace <leaves>[distance=7,persistent=false]`, which reports how many
blocks matched. Nothing should match, so the tree is still standing afterwards; the total leaf
count is measured separately with `clone ... filtered <leaves> normal`, which does not touch the
tree. The clone writes its copy to a deck far above the tree, because a clone that lands on the
tree would overwrite the level above it and change the very leaves that are being measured.

Usage: smoke_leaves.py [host] [port] [password]
"""

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon import Rcon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEATURES = os.path.join(ROOT, "src", "main", "resources", "data", "terrainrefreshed", "worldgen", "configured_feature")

BASE_Y = 140
DECK_Y = 260
CLONED = re.compile(r"cloned (\d+)")
FILLED = re.compile(r"Successfully filled (\d+)")


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
            "leaf": config["leaves"]["Name"],
            "log": config["trunk"]["Name"],
            "max_height": config["max_height"],
            "radius": config["canopy_radius"],
        })

    return found


def count(rcon, block, x, y, z, reach):
    """How many blocks of one type sit in a slice, without disturbing them."""
    answer = rcon.command(
        "clone %d %d %d %d %d %d %d %d %d filtered %s normal"
        % (x - reach, y, z - reach, x + reach, y, z + reach, x - reach, DECK_Y, z - reach, block)
    )
    found = CLONED.search(answer)

    if found is not None:
        return int(found.group(1))

    if "No blocks were cloned" in answer:
        return 0

    raise RuntimeError("clone %s -> %s" % (block, answer))


def decaying(rcon, leaf, x, y, z, reach, top):
    """How many leaves in the box sit in the state the game removes them in."""
    answer = rcon.command(
        "fill %d %d %d %d %d %d minecraft:air replace %s[distance=7,persistent=false]"
        % (x - reach, y, z - reach, x + reach, top, z + reach, leaf)
    )
    found = FILLED.search(answer)

    if found is not None:
        return int(found.group(1))

    if "No blocks were filled" in answer:
        return 0

    raise RuntimeError("fill %s -> %s" % (leaf, answer))


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25576
    password = sys.argv[3] if len(sys.argv) > 3 else "terrainrefreshed"

    rcon = Rcon(host, port, password)
    failures = []
    total_leaves = 0

    try:
        rcon.command("forceload add 0 0")

        for tree in species():
            reach = tree["radius"] + 3
            top = BASE_Y + tree["max_height"] + tree["radius"] + 3
            x = 0
            z = 0

            rcon.command("fill %d %d %d %d %d %d minecraft:air" % (
                x - reach, BASE_Y - 2, z - reach, x + reach, top, z + reach))
            rcon.command("fill %d %d %d %d %d %d minecraft:air" % (
                x - reach, DECK_Y, z - reach, x + reach, DECK_Y + 1, z + reach))
            rcon.command("place feature terrainrefreshed:%s %d %d %d" % (tree["id"], x, BASE_Y, z))

            # The game updates the leaf distances on the tick after the leaves are placed, and the
            # distance of one leaf depends on the distance its neighbours were given, so the wave
            # needs a few ticks to settle.
            time.sleep(4)

            leaves = 0
            logs = 0
            for y in range(BASE_Y - 1, top + 1):
                leaves += count(rcon, tree["leaf"], x, y, z, reach)
                logs += count(rcon, tree["log"], x, y, z, reach)

            doomed = decaying(rcon, tree["leaf"], x, BASE_Y - 1, z, reach, top)
            total_leaves += leaves

            status = "ok" if doomed == 0 and leaves > 0 and logs > 0 else "FAIL"
            print("%-22s leaves=%-5d logs=%-5d decaying=%-3d %s" % (tree["id"], leaves, logs, doomed, status))

            if status == "FAIL":
                failures.append(tree["id"])
    finally:
        rcon.close()

    print("total leaves %d, species with decaying leaves: %s" % (total_leaves, ", ".join(failures) or "none"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
