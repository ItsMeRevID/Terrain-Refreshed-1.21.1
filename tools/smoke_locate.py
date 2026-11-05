#!/usr/bin/env python3
"""Asks the running dev server to locate every Terrain Refreshed biome.

`/locate biome` walks the multi-noise source outwards until it finds a matching
biome, so a hit proves that the biome is reachable in the generated world and
that the runtime injection put it into the biome list.

Each search is a fresh spiral over the whole climate list, so a full sweep of all
100 biomes takes tens of minutes. Pass a limit to only check that many, spread
across the alphabet, when a quick sample is enough.

Usage: smoke_locate.py [host] [port] [password] [limit]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcon import Rcon  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIOMES = os.path.join(ROOT, "src", "main", "resources", "data", "terrainrefreshed", "worldgen", "biome")


def sample(ids, limit):
    if limit <= 0 or limit >= len(ids):
        return ids

    step = len(ids) / limit
    return [ids[int(index * step)] for index in range(limit)]


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25576
    password = sys.argv[3] if len(sys.argv) > 3 else "terrainrefreshed"
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    todo = sorted(name[:-5] for name in os.listdir(BIOMES) if name.endswith(".json"))
    ids = sample(todo, limit)
    if len(ids) != len(todo):
        print("sampling %d of %d biomes" % (len(ids), len(todo)))

    rcon = Rcon(host, port, password)
    found = []
    missing = []
    try:
        for biome in ids:
            answer = rcon.command("locate biome terrainrefreshed:%s" % biome).strip()
            if "could not find" in answer.lower() or not answer:
                missing.append(biome)
                print("MISSING %s" % biome)
            else:
                found.append(biome)
                print("FOUND   %-24s %s" % (biome, answer))
    finally:
        rcon.close()

    print("found %d / %d" % (len(found), len(ids)))
    if missing:
        print("missing: " + ", ".join(missing))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
