#!/usr/bin/env python3
"""Probes the running dev server for biomes and placed blocks over RCON.

The `execute` conditions take the position before the value in 26.3, so the probe
reads `execute if biome <x> <y> <z> <biome>`. The condition succeeds silently, so
the probe appends `run seed`: the world seed is echoed back as command feedback
only when the condition held, which turns the RCON response into a boolean.

Usage: smoke_probe.py [host] [port] [password]

The grid sits inside the 129x129 area the smoke test force loads, so it reports how much of the
immediate spawn neighbourhood the new biomes claim. A low count is not a failure: reachability is
the locate sweep's job, and it searches 6400 blocks in every direction.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon import Rcon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIOMES = os.path.join(ROOT, "src", "main", "resources", "data", "terrainrefreshed", "worldgen", "biome")

POSITIONS = [(0, 0), (-48, 0), (48, 0), (0, 48), (0, -48), (32, 32)]

BLOCK_PROBES = [
    ("minecraft:oak_log", 0, 0),
    ("minecraft:dark_oak_log", 16, 16),
    ("minecraft:water", 32, 32),
    ("minecraft:gravel", 32, 32),
]


def probe(rcon, block, x, z, y_range):
    template = "execute if block %d %%d %d %s run seed" % (x, z, block)
    for y in y_range:
        answer = rcon.command(template % y).strip()
        if answer:
            return y, answer
    return None, ""


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25576
    password = sys.argv[3] if len(sys.argv) > 3 else "terrainrefreshed"

    ids = sorted(name[:-5] for name in os.listdir(BIOMES) if name.endswith(".json"))
    rcon = Rcon(host, port, password)
    found = []
    try:
        for x, z in POSITIONS:
            for biome in ids:
                answer = rcon.command("execute if biome %d 64 %d terrainrefreshed:%s run seed" % (x, z, biome)).strip()
                if answer:
                    found.append((x, z, biome))
                    print("MATCH  at (%d,%d) -> %s" % (x, z, biome))

        for block, x, z in BLOCK_PROBES:
            y, answer = probe(rcon, block, x, z, range(56, 124))
            if y is None:
                print("MISSING block %s at (%d,%d)" % (block, x, z))
            else:
                print("BLOCK  %s at (%d,%d,%d)" % (block, x, y, z))
    finally:
        rcon.close()

    print("spawn area: %d of %d grid positions hold a Terrain Refreshed biome" % (len(found), len(POSITIONS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
