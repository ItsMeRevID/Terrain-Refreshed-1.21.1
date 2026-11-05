#!/usr/bin/env python3
"""Measures how densely the Terrain Refreshed biomes are spread through the world.

`/locate biome` searches a fixed box around the command origin, so a single search from spawn says
only whether a biome appears nearby. This probe runs the same search from a lattice of origins and
reports, per biome, how many of those searches hit and the smallest distance reported. A biome that
hits from every origin is common; one that never hits at all is not being generated, however the
climate list verifies it.

Usage: smoke_density.py [host] [port] [password] [biome ... | count]

A single number samples that many biomes spread over the whole set; the default probes all of them.
Six origins per biome is a lot of searches, so keep the count small unless the server is idle.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon import Rcon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIOME_DIR = os.path.join(ROOT, "src", "main", "resources", "data", "terrainrefreshed", "worldgen", "biome")
DISTANCE = re.compile(r"\((\d+) blocks away\)")
ORIGINS = [(0, 0), (16384, 0), (-16384, 0), (0, 16384), (0, -16384), (12288, 12288)]


def biome_ids():
    return sorted(name[:-5] for name in os.listdir(BIOME_DIR) if name.endswith(".json"))


def sample(ids, count):
    count = max(1, min(count, len(ids)))
    step = len(ids) / float(count)
    return [ids[int(index * step)] for index in range(count)]


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25576
    password = sys.argv[3] if len(sys.argv) > 3 else "terrainrefreshed"
    biomes = sys.argv[4:]
    if len(biomes) == 1 and biomes[0].isdigit():
        biomes = sample(biome_ids(), int(biomes[0]))
    elif not biomes:
        biomes = biome_ids()

    rcon = Rcon(host, port, password)
    missed = []
    try:
        for biome in biomes:
            hits = []
            misses = 0
            for x, z in ORIGINS:
                answer = rcon.command(
                    "execute in minecraft:overworld positioned %d 64 %d run locate biome terrainrefreshed:%s"
                    % (x, z, biome)
                ).strip()
                found = DISTANCE.search(answer)
                if found:
                    hits.append(int(found.group(1)))
                else:
                    misses += 1
                    if misses == 1:
                        failure = answer

            if len(hits) == 0:
                missed.append(biome)
                print("%-24s hit 0/%d origins -> %s" % (biome, len(ORIGINS), failure))
            else:
                print("%-24s hit %d/%d origins, nearest %d blocks, median %d" % (
                    biome, len(hits), len(ORIGINS), min(hits),
                    sorted(hits)[len(hits) // 2]))
    finally:
        rcon.close()

    if missed:
        print("never found: " + ", ".join(missed))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
