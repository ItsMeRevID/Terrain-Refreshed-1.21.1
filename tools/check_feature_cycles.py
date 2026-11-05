"""Reproduce the game's feature-order cycle check over every biome.

The game chains the placed features of each biome into one long list and topologically sorts it.
Two biomes that share features in a different relative order create a cycle, and a cycle aborts
world loading. This checks the 1.21.1 vanilla biomes together with the Terrain Refreshed ones.

Run it from the 1.21.1 project: python tools/check_feature_cycles.py
"""

import json
import os
import sys
import zipfile

MC_JAR = os.path.expanduser("~/.gradle/caches/fabric-loom/1.21.1/minecraft-extracted_server.jar")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = os.path.join(ROOT, "src", "main", "resources", "data", "terrainrefreshed", "worldgen", "biome")


def vanilla_biomes():
    with zipfile.ZipFile(MC_JAR) as archive:
        return {
            entry.rsplit("/", 1)[1][:-5]: json.loads(archive.read(entry))
            for entry in archive.namelist()
            if entry.startswith("data/minecraft/worldgen/biome/") and entry.endswith(".json")
        }


def mod_biomes():
    out = {}

    for name in sorted(os.listdir(MOD)):
        with open(os.path.join(MOD, name), encoding="utf-8") as fh:
            out[name[:-5]] = json.load(fh)

    return out


def chain(biome):
    return [feature for step in biome["features"] for feature in step]


def edges_for(biomes):
    edges = {}

    for biome in biomes.values():
        flat = chain(biome)

        for first, second in zip(flat, flat[1:]):
            edges.setdefault(first, set()).add(second)

    return edges


def find_cycle(edges):
    colour = {}
    stack = []

    def visit(node):
        colour[node] = 1
        stack.append(node)

        for nxt in sorted(edges.get(node, ())):
            state = colour.get(nxt, 0)

            if state == 1:
                return stack[stack.index(nxt):] + [nxt]

            if state == 0:
                found = visit(nxt)

                if found:
                    return found

        colour[node] = 2
        stack.pop()
        return None

    for node in sorted(edges):
        if colour.get(node, 0) == 0:
            found = visit(node)

            if found:
                return found

    return None


def main():
    vanilla = vanilla_biomes()
    mod = mod_biomes()

    cycle = find_cycle(edges_for(vanilla))

    if cycle:
        print("the vanilla 1.21.1 biomes already cycle, which cannot be true:")
        for node in cycle:
            print("  %s" % node)
        return 1

    for name, biome in mod.items():
        if len(biome["features"]) != 11:
            print("%s has %d feature steps, 1.21.1 wants 11" % (name, len(biome["features"])))
            return 1

    biomes = dict(vanilla)
    biomes.update(mod)
    cycle = find_cycle(edges_for(biomes))

    if not cycle:
        print("no cycle over %d biomes (%d vanilla + %d mod, %d placed features)"
              % (len(biomes), len(vanilla), len(mod),
                 len({f for biome in biomes.values() for f in chain(biome)})))
        return 0

    print("cycle:")

    for node in cycle:
        print("  %s" % node)

    return 1


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    sys.exit(main())
