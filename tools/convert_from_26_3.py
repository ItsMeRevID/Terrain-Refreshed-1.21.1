"""Rewrite the 26.3 data pack into the Minecraft 1.21.1 schema.

The authored content (biome list, colours, vegetation, densities, tree configs) is generated once by
the 26.3 project's tools/generate_content.py. This tool only moves that content across the schema
changes between the two versions, so the 1.21.1 pack cannot drift from what was verified on 26.3:

  configured features   worldgen/feature + flat fields -> worldgen/configured_feature + "config",
                        block states {id, properties} -> {Name, Properties}
  noise                 base_octave/base_amplitude/amplitude_modifiers -> firstOctave/amplitudes
  density functions     input/left/right -> argument/argument1/argument2,
                        gradient -> y_clamped_gradient, noise+shift_* -> shifted_noise,
                        constant "value" -> "argument"
  biomes                carvers list -> {"air": [...]}, attributes sky colour -> effects,
                        hex colours -> integers, 1.21.1 mob spawns added, and every vanilla
                        placed feature 1.21.1 does not know is dropped.
  density overrides     the three sloped_cheese files are patched onto the *1.21.1* vanilla graphs
                        rather than translated, so the untouched half of the expression stays vanilla.

Everything the conversion emits is checked against the 1.21.1 server jar while it runs: referenced
vanilla density functions, noise and placed features must exist, and any density node without a
1.21.1 translation aborts the run.

Run it from the 1.21.1 project: python tools/convert_from_26_3.py
"""

import argparse
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_FROM = os.path.join(os.path.dirname(ROOT), "src", "main", "resources", "data")
DEFAULT_TO = os.path.join(ROOT, "src", "main", "resources", "data")
DEFAULT_JAR = os.path.expanduser("~/.gradle/caches/fabric-loom/1.21.1/minecraft-extracted_server.jar")

MOD = "terrainrefreshed"

# The half of the vanilla density graph the mod adds relief to, and the mod's own entry point.
BASE_3D_NOISE = "minecraft:overworld/base_3d_noise"
TERRAIN_FEATURES = MOD + ":terrain_features"
PRESETS = ("overworld", "overworld_amplified", "overworld_large_biomes")

# 1.21.1 density types: unary takes "argument", binary takes "argument1"/"argument2".
ARGUMENT_TYPES = {
    "abs", "square", "cube", "half_negative", "quarter_negative", "squeeze",
    "interpolated", "flat_cache", "cache_2d", "cache_once", "cache_all_in_cell",
    "shift", "shift_a", "shift_b", "blend_density",
}
BINARY_TYPES = {"add", "mul", "min", "max"}
# Types whose child is still called "input" in 1.21.1.
INPUT_TYPES = {"clamp", "range_choice", "weird_scaled_sampler"}
# Types that carry no density children and are copied field for field.
LEAF_TYPES = {"blend_alpha", "blend_offset", "end_islands", "beardifier", "noise", "old_blended_noise"}

# Configured-feature fields holding a block state.
BLOCK_STATE_KEYS = ("trunk", "leaves", "water", "bed")

# Which 1.21.1 biome's mobs a Terrain Refreshed category inherits.
SPAWN_TEMPLATES = {
    "meadow": "minecraft:meadow",
    "forest": "minecraft:forest",
    "wetland": "minecraft:swamp",
    "arid": "minecraft:desert",
    "rock": "minecraft:windswept_hills",
    "jungle": "minecraft:jungle",
    "savanna": "minecraft:savanna",
}


class Reference:
    """What the 1.21.1 game actually ships, so the conversion can be checked while it runs."""

    def __init__(self, jar):
        self.biomes = {}
        self.placed = set()
        self.noise = set()
        self.density = {}

        with zipfile.ZipFile(jar) as archive:
            for entry in archive.namelist():
                parts = entry.split("/")

                if entry.startswith("data/minecraft/worldgen/") and entry.endswith(".json") and len(parts) > 4:
                    kind, tail = parts[3], "/".join(parts[4:-1])
                    name = parts[-1][:-5]
                    full = "minecraft:" + ("%s/%s" % (tail, name) if tail else name)
                    doc = json.loads(archive.read(entry))

                    if kind == "biome":
                        self.biomes[name] = doc
                    elif kind == "placed_feature":
                        self.placed.add(full)
                    elif kind == "noise":
                        self.noise.add(full)
                    elif kind == "density_function":
                        self.density[full] = doc

        self.order = self.vanilla_feature_order()

    def vanilla_feature_order(self):
        """The one feature sequence the game can build without a cycle, straight from vanilla.

        Every biome chains its placed features and the generator topologically sorts all those
        chains together, so two biomes that list the same pair in a different relative order abort
        world loading. Sorting each converted vegetation list to this order keeps us compatible.
        """
        edges = {}
        nodes = set()

        for biome in self.biomes.values():
            chain = [feature for step in biome["features"] for feature in step]
            nodes.update(chain)

            for first, second in zip(chain, chain[1:]):
                edges.setdefault(first, set()).add(second)

        incoming = {node: 0 for node in nodes}

        for sources, targets in edges.items():
            for target in targets:
                incoming[target] += 1

        ready = sorted(node for node, count in incoming.items() if count == 0)
        order = {}

        while ready:
            node = ready.pop(0)
            order[node] = len(order)

            for target in sorted(edges.get(node, ())):
                incoming[target] -= 1

                if not incoming[target]:
                    ready.append(target)

            ready.sort()

        if len(order) != len(nodes):
            raise SystemExit("vanilla 1.21.1 feature order is not acyclic, cannot use it as a template")

        return order

    def biome(self, key):
        name = key.split(":", 1)[1]

        if name not in self.biomes:
            raise SystemExit("1.21.1 has no biome %s to copy mob spawns from" % key)

        return self.biomes[name]

    def require_density(self, ref, where):
        if ref.startswith("minecraft:") and ref not in self.density:
            raise SystemExit("%s references unknown vanilla density function %s" % (where, ref))

    def require_noise(self, ref, where):
        if ref.startswith("minecraft:") and ref not in self.noise:
            raise SystemExit("%s references unknown vanilla noise %s" % (where, ref))

    def require_placed(self, ref):
        return ref.startswith(MOD + ":") or ref in self.placed


def short(type_id):
    return type_id.split(":", 1)[1] if ":" in type_id else type_id


def blockstate(value):
    if isinstance(value, str):
        return {"Name": value}

    out = {"Name": value["id"]}

    if value.get("properties"):
        out["Properties"] = value["properties"]

    return out


def colour(value):
    return int(value.replace("#", ""), 16)


def rewrite_density(doc, ref, where):
    if isinstance(doc, str):
        ref.require_density(doc, where)
        return doc

    if not isinstance(doc, dict):
        return doc

    kind = short(doc.get("type", ""))
    out = {}

    if kind == "gradient":
        assert doc["axis"] == "y", "%s: 1.21.1 only has the y clamped gradient" % where
        out["type"] = "minecraft:y_clamped_gradient"
        out["from_y"] = doc["from_coordinate"]
        out["to_y"] = doc["to_coordinate"]
        out["from_value"] = doc["from_value"]
        out["to_value"] = doc["to_value"]
        return out

    if kind == "noise" and any(key in doc for key in ("shift_x", "shift_z", "shift_y")):
        out["type"] = "minecraft:shifted_noise"
        out["noise"] = doc["noise"]
        out["shift_x"] = doc.get("shift_x", 0.0)
        out["shift_y"] = doc.get("shift_y", 0.0)
        out["shift_z"] = doc.get("shift_z", 0.0)
        out["xz_scale"] = doc["xz_scale"]
        out["y_scale"] = doc["y_scale"]
        ref.require_noise(doc["noise"], where)
        return out

    if kind == "constant":
        # 26.3 names the value "value"; 1.21.1's single-argument codec names it "argument".
        return {"type": "minecraft:constant", "argument": doc["value"]}

    if kind in BINARY_TYPES:
        out["type"] = doc["type"]
        out["argument1"] = rewrite_density(doc["left"], ref, where)
        out["argument2"] = rewrite_density(doc["right"], ref, where)
        return out

    if kind in ARGUMENT_TYPES:
        out["type"] = doc["type"]
        out["argument"] = rewrite_density(doc["input"], ref, where)
        return out

    if kind in INPUT_TYPES or kind == "spline" or kind in LEAF_TYPES:
        out["type"] = doc["type"]

        for key, value in doc.items():
            if key == "type":
                continue

            if kind == "spline":
                out[key] = rewrite_spline(value, ref, where)
            elif key == "noise":
                out[key] = value
                ref.require_noise(value, where)
            else:
                out[key] = rewrite_density(value, ref, where)

        return out

    raise SystemExit("%s: no 1.21.1 translation for density type %s" % (where, doc.get("type")))


def rewrite_spline(spline, ref, where):
    out = {}

    for key, value in spline.items():
        if key == "points":
            out["points"] = [rewrite_point(point, ref, where) for point in value]
        else:
            out[key] = rewrite_density(value, ref, where)

    return out


def rewrite_point(point, ref, where):
    """A spline knot: location and derivative are plain numbers, only the value may be a graph."""
    out = dict(point)

    if isinstance(out.get("value"), (dict, str)):
        out["value"] = rewrite_density(out["value"], ref, where)

    return out


def rewrite_noise(doc):
    amplitudes = [round(a * doc["base_amplitude"], 6) for a in doc["amplitude_modifiers"]]

    assert doc["octave_count"] == len(amplitudes), "noise octave count does not match the modifiers"

    return {"firstOctave": doc["base_octave"], "amplitudes": amplitudes}


def rewrite_configured(doc):
    config = {key: value for key, value in doc.items() if key != "type"}

    for key in BLOCK_STATE_KEYS:
        if isinstance(config.get(key), (dict, str)):
            config[key] = blockstate(config[key])

    return {"type": doc["type"], "config": config}


def rewrite_placed(doc):
    placement = []

    for step in doc["placement"]:
        step = json.loads(json.dumps(step))

        if isinstance(step.get("predicate"), dict) and "state" in step["predicate"]:
            step["predicate"]["state"] = blockstate(step["predicate"]["state"])

        placement.append(step)

    return {"feature": doc["feature"], "placement": placement}


def rewrite_biome(biome_id, doc, ref, category, report):
    template = ref.biome(SPAWN_TEMPLATES[category])
    effects = template["effects"]

    out = {
        "fog_color": effects["fog_color"],
        "sky_color": colour(doc["attributes"]["minecraft:visual/sky_color"]),
        "water_color": colour(doc["effects"]["water_color"]),
        "water_fog_color": effects["water_fog_color"],
    }

    for key in ("foliage_color", "grass_color", "grass_color_modifier"):
        if key in doc["effects"]:
            out[key] = colour(doc["effects"][key]) if key.endswith("_color") else doc["effects"][key]

    for key in ("mood_sound", "particle", "music"):
        if key in effects:
            out[key] = effects[key]

    if "dry_foliage_color" in doc["effects"]:
        report["dropped_colour"].append(biome_id)

    features = []

    for step_index, step in enumerate(doc["features"]):
        kept = []

        for feature in step:
            if ref.require_placed(feature):
                kept.append(feature)
            else:
                report["dropped_features"].append(feature)

        own = [(index, feature) for index, feature in enumerate(kept) if feature.startswith(MOD + ":")]
        vanilla = [feature for feature in kept if not feature.startswith(MOD + ":")]
        ranked = sorted(vanilla, key=lambda feature: ref.order.get(feature, len(ref.order)))

        if ranked != vanilla:
            report["resequenced"].append("%s step %d" % (biome_id, step_index))

        for index, feature in own:
            ranked.insert(min(index, len(ranked)), feature)

        features.append(ranked)

    biome = {
        "carvers": {"air": doc["carvers"]},
        "downfall": doc["downfall"],
        "effects": out,
        "features": features,
        "has_precipitation": doc["has_precipitation"],
        "spawn_costs": template["spawn_costs"],
        "spawners": template["spawners"],
        "temperature": doc["temperature"],
    }

    return biome


def patch_sloped_cheese(preset, ref, dst):
    """Add the mod's relief to the untouched 1.21.1 vanilla graph instead of translating 26.3's."""
    doc = ref.density["minecraft:%s/sloped_cheese" % preset]
    hits = []

    def inject(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if value == BASE_3D_NOISE:
                    hits.append(key)
                    node[key] = {"type": "minecraft:add", "argument1": BASE_3D_NOISE, "argument2": TERRAIN_FEATURES}
                else:
                    inject(value)

        elif isinstance(node, list):
            for value in node:
                inject(value)

        return node

    patched = inject(json.loads(json.dumps(doc)))
    assert len(hits) == 1, "%s: expected one %s reference, found %d" % (preset, BASE_3D_NOISE, len(hits))

    target = os.path.join(dst, "minecraft", "worldgen", "density_function", preset)
    os.makedirs(target, exist_ok=True)

    with open(os.path.join(target, "sloped_cheese.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(patched, fh, indent=2, sort_keys=True)
        fh.write("\n")


def load_categories(tools_dir):
    """Read the authored category of every biome out of the generator that wrote it."""
    sys.path.insert(0, tools_dir)
    import generate_content

    return {b["id"]: b["cat"] for b in generate_content.BIOMES}


def convert(src, dst, ref, categories):
    report = {"dropped_features": [], "dropped_colour": [], "resequenced": []}
    written = 0

    def read(*parts):
        with open(os.path.join(src, *parts), encoding="utf-8") as fh:
            return json.load(fh)

    def write(kind, name, doc):
        target = os.path.join(dst, MOD, kind)
        os.makedirs(target, exist_ok=True)

        with open(os.path.join(target, name + ".json"), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(doc, fh, indent=2, sort_keys=True)
            fh.write("\n")

    for name in sorted(os.listdir(os.path.join(src, MOD, "worldgen", "feature"))):
        write("worldgen/configured_feature", name[:-5], rewrite_configured(read(MOD, "worldgen", "feature", name)))
        written += 1

    for name in sorted(os.listdir(os.path.join(src, MOD, "worldgen", "placed_feature"))):
        write("worldgen/placed_feature", name[:-5], rewrite_placed(read(MOD, "worldgen", "placed_feature", name)))
        written += 1

    for name in sorted(os.listdir(os.path.join(src, MOD, "worldgen", "noise"))):
        write("worldgen/noise", name[:-5], rewrite_noise(read(MOD, "worldgen", "noise", name)))
        written += 1

    for name in sorted(os.listdir(os.path.join(src, MOD, "worldgen", "density_function"))):
        doc = read(MOD, "worldgen", "density_function", name)
        write("worldgen/density_function", name[:-5], rewrite_density(doc, ref, name))
        written += 1

    for preset in PRESETS:
        patch_sloped_cheese(preset, ref, dst)
        written += 1

    for name in sorted(os.listdir(os.path.join(src, MOD, "worldgen", "biome"))):
        biome_id = name[:-5]
        doc = read(MOD, "worldgen", "biome", name)
        write("worldgen/biome", biome_id, rewrite_biome(biome_id, doc, ref, categories[biome_id], report))
        written += 1

    return report, written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="src", default=DEFAULT_FROM, help="26.3 data directory")
    parser.add_argument("--to", dest="dst", default=DEFAULT_TO, help="1.21.1 data directory")
    parser.add_argument("--jar", default=DEFAULT_JAR, help="Minecraft 1.21.1 server jar for the vanilla reference")
    parser.add_argument("--generator", default=os.path.join(os.path.dirname(ROOT), "tools"),
                        help="directory holding generate_content.py")
    args = parser.parse_args()

    ref = Reference(args.jar)
    categories = load_categories(args.generator)
    report, written = convert(args.src, args.dst, ref, categories)

    print("converted %d files against %d vanilla placed features, %d density functions"
          % (written, len(ref.placed), len(ref.density)))

    if report["dropped_features"]:
        counts = {}

        for feature in report["dropped_features"]:
            counts[feature] = counts.get(feature, 0) + 1

        print("vanilla placed features 1.21.1 does not have, dropped from the biome lists:")

        for feature, count in sorted(counts.items(), key=lambda item: -item[1]):
            print("  - %s (%d biome(s))" % (feature, count))

    if report["dropped_colour"]:
        print("dry_foliage_color dropped from %d biome(s): no such field in 1.21.1" % len(report["dropped_colour"]))

    print("vanilla lists re-sequenced to the 1.21.1 feature order: %d biome step(s)" % len(report["resequenced"]))

    return 0


if __name__ == "__main__":
    sys.exit(main())
