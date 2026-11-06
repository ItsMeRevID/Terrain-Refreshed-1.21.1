#!/usr/bin/env python3
"""Measures the generated surface and the biome at a set of positions.

The same probe runs against a vanilla server and a modded one so the two can be compared
column by column. The surface height is found by walking down from the build limit and
stopping at the first block that is not air; the chunks are force loaded first, because a
block in an unloaded chunk answers every condition with a failure.

The biome is found by asking the server about every candidate, because the game has no
command that prints the biome of a position. Only a numeric answer counts: the command
answers with the world seed when the condition held and with an error line when the biome
id does not exist on that server.

Usage: terrain_probe.py <host> <port> <password> [candidates.txt] [out.txt]
"""

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon import Rcon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIOMES = os.path.join(ROOT, "src", "main", "resources", "data", "terrainrefreshed", "worldgen", "biome")

POSITIONS = [(0, 0), (120, 60), (-240, 310), (500, -520), (-800, -800)]

VANILLA_CANDIDATES = [
    "plains", "forest", "flower_forest", "birch_forest", "dark_forest", "taiga",
    "snowy_plains", "snowy_taiga", "desert", "savanna", "swamp", "beach", "ocean",
    "river", "frozen_ocean", "windswept_hills", "meadow", "grove", "stony_peaks",
    "mangrove_swamp", "cherry_grove", "old_growth_pine_taiga", "lush_caves",
    "sunflower_plains", "birch_forest", "dark_forest", "snowy_slopes", "steep_ravine",
]

HELD = "Seed:"


def candidates(path):
    ids = list(VANILLA_CANDIDATES)

    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as handle:
            ids += [line.strip() for line in handle if line.strip()]
    elif os.path.isdir(BIOMES):
        ids += sorted(name[:-5] for name in os.listdir(BIOMES) if name.endswith(".json"))

    return ids


def force_load(rcon, x, z):
    # forceload takes block positions and converts them to chunks itself.
    rcon.command("forceload add %d %d %d %d" % (x, z, x, z))


def wait_for_chunk(rcon, x, z, timeout=120):
    """A force loaded chunk is generated in the background, so the column only answers
    once the server has built it."""
    deadline = time.time() + timeout

    while time.time() < deadline:
        answer = rcon.command("execute if block %d 319 %d minecraft:air run seed" % (x, z)).strip()
        if HELD in answer:
            return True
        time.sleep(2)

    return False


def surface_height(rcon, x, z):
    for y in range(319, -65, -1):
        answer = rcon.command("execute if block %d %d %d minecraft:air run seed" % (x, y, z)).strip()
        if HELD in answer:
            continue
        if answer:
            return None
        return y
    return None


def biome_at(rcon, x, z, ids):
    for biome in ids:
        answer = rcon.command("execute if biome %d 64 %d %s run seed" % (x, z, biome)).strip()
        if HELD in answer:
            return biome
    return "unknown"


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25577
    password = sys.argv[3] if len(sys.argv) > 3 else "terrainrefreshed"
    list_path = sys.argv[4] if len(sys.argv) > 4 else None
    out_path = sys.argv[5] if len(sys.argv) > 5 else None

    ids = candidates(list_path)
    rcon = Rcon(host, port, password)
    rows = []
    try:
        for x, z in POSITIONS:
            force_load(rcon, x, z)

        for x, z in POSITIONS:
            if not wait_for_chunk(rcon, x, z):
                print("chunk at (%d,%d) never came up" % (x, z))

            height = surface_height(rcon, x, z)
            biome = biome_at(rcon, x, z, ids)
            rows.append("%d,%d,%s,%s" % (x, z, height, biome))
            print("%d,%d,%s,%s" % (x, z, height, biome))
            sys.stdout.flush()
    finally:
        rcon.close()

    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(rows) + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
