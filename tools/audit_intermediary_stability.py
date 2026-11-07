"""Check that every Minecraft class and member the built mod calls keeps its intermediary name.

A Fabric mod is compiled against one Minecraft version and the loader ships it to every other
version unchanged. The contract that makes that work is intermediary: the mod's bytecode calls
``method_49507`` and the running game still has that name for the same member. Intermediary is
regenerated for every Minecraft release, so a member that Mojang renamed between 1.21.1 and 1.21.8
can change its intermediary name too, and the mod then dies with a NoSuchMethodError on a version
where nothing in the mod changed.

The check reads the built jar, whose bytecode already uses intermediary names, and compares every
referenced class, method and field against the intermediary mappings of each 1.21.x release. The
mixin targets in the refmap are checked as well, because a mixin target is a string in the
annotation and never shows up as a call in the bytecode.

Names are compared through intermediary rather than through the Mojang names, because Mojang
renames a class without touching its intermediary name: ``ResourceLocation`` became ``Identifier``
in 1.21.11 and stayed ``class_2960`` all the same.

Run it from the 1.21.1 project: python tools/audit_intermediary_stability.py
"""

import argparse
import json
import os
import re
import struct
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_JAR = os.path.join(ROOT, "build", "libs")
DEFAULT_CACHE = os.path.join(ROOT, "build", "audit-cache")

VERSIONS = [
    "1.21.1", "1.21.2", "1.21.3", "1.21.4", "1.21.5", "1.21.6",
    "1.21.7", "1.21.8", "1.21.9", "1.21.10", "1.21.11",
]

INTERMEDIARY_MAVEN = "https://maven.fabricmc.net/net/fabricmc/intermediary/%s/intermediary-%s-v2.jar"
MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

CONSTANT_UTF8 = 1
CONSTANT_CLASS = 7
CONSTANT_FIELDREF = 9
CONSTANT_METHODREF = 10
CONSTANT_NAME_AND_TYPE = 12


class ClassFile:
    """The constant pool of a compiled class, enough to list the Minecraft members it calls."""

    def __init__(self, data):
        self.utf8 = {}
        self.classes = {}
        self.refs = []

        self._parse(data)

    def _parse(self, data):
        count = struct.unpack_from(">H", data, 8)[0]
        offset = 10
        index = 1
        name_types = {}
        members = {}

        while index < count:
            tag = data[offset]
            offset += 1

            if tag == CONSTANT_UTF8:
                length = struct.unpack_from(">H", data, offset)[0]
                offset += 2
                self.utf8[index] = data[offset:offset + length].decode("utf-8", "replace")
                offset += length
            elif tag == CONSTANT_CLASS:
                self.classes[index] = struct.unpack_from(">H", data, offset)[0]
                offset += 2
            elif tag == 8:
                offset += 2
            elif tag in (CONSTANT_FIELDREF, CONSTANT_METHODREF):
                class_index, name_type_index = struct.unpack_from(">HH", data, offset)
                members[index] = (tag, class_index, name_type_index)
                offset += 4
            elif tag == CONSTANT_NAME_AND_TYPE:
                name_types[index] = struct.unpack_from(">HH", data, offset)
                offset += 4
            elif tag == 3 or tag == 4:
                offset += 4
            elif tag in (5, 6):
                offset += 8
                index += 1
            elif tag in (11, 17, 18):
                offset += 4
            elif tag == 15:
                offset += 3
            elif tag in (16, 19, 20):
                offset += 2
            else:
                raise ValueError("unknown constant pool tag %d" % tag)

            index += 1

        for tag, class_index, name_type_index in members.values():
            name_index, descriptor_index = name_types[name_type_index]
            self.refs.append((tag, class_index, name_index, descriptor_index))

    def text(self, index):
        return self.utf8[index]


def read_members(data):
    """The Minecraft classes and members a compiled class file touches."""
    pool = ClassFile(data)

    classes = set()
    refs = set()

    for name_index in pool.classes.values():
        name = pool.text(name_index)

        if name.startswith("net/minecraft/"):
            classes.add(name)

    for tag, class_index, name_index, descriptor_index in pool.refs:
        owner = pool.text(pool.classes[class_index])

        if not owner.startswith("net/minecraft/"):
            continue

        kind = "method" if tag == CONSTANT_METHODREF else "field"
        refs.add((owner, pool.text(name_index), pool.text(descriptor_index), kind))

    return classes, refs


def scan_jar(path):
    classes = set()
    refs = set()

    with zipfile.ZipFile(path) as archive:
        for entry in archive.namelist():
            if not entry.endswith(".class"):
                continue

            found_classes, found_refs = read_members(archive.read(entry))
            classes |= found_classes
            refs |= found_refs

    return classes, refs


def scan_refmap(path):
    """The intermediary classes, methods and descriptors the mixin asks the game to touch."""
    classes = set()
    members = set()

    with zipfile.ZipFile(path) as archive:
        for entry in archive.namelist():
            if not entry.endswith(".refmap.json"):
                continue

            document = json.loads(archive.read(entry))

            for section in [document.get("mappings", {})] + list(document.get("data", {}).values()):
                for entries in section.values():
                    for value in entries.values():
                        for owner in re.findall(r"L([\w/$]+);", value):
                            classes.add(owner)

                        for descriptor in re.findall(r"(?:method|field)_\d+\([^)]*\)[^;]*;", value):
                            members.add(descriptor)

    return classes, members


class Intermediary:
    """The intermediary mappings of one version: obfuscated name -> intermediary name."""

    def __init__(self, path):
        self.class_to_intermediary = {}
        self.intermediary_to_obfuscated = {}
        self.member_descriptors = {}
        self.members = {}
        current_obfuscated = None
        current_intermediary = None

        with zipfile.ZipFile(path) as archive:
            name = [entry for entry in archive.namelist() if entry.endswith(".tiny")][0]
            text = archive.read(name).decode("utf-8", "replace")

        for line in text.splitlines():
            parts = line.lstrip("\t").split("\t")

            if not parts or not parts[0]:
                continue

            if parts[0] == "c" and len(parts) >= 3:
                current_obfuscated = parts[1]
                current_intermediary = parts[2]
                self.class_to_intermediary[parts[1]] = parts[2]
                self.intermediary_to_obfuscated[parts[2]] = parts[1]
            elif parts[0] in ("m", "f") and len(parts) >= 4 and current_obfuscated is not None:
                self.members.setdefault((current_intermediary, parts[3]), []).append(parts[1])
                self.member_descriptors.setdefault(parts[3], set()).add(parts[1])

    def has_class(self, intermediary_class):
        return intermediary_class in self.intermediary_to_obfuscated

    def descriptors(self, intermediary_class, intermediary_member):
        return self.members.get((intermediary_class, intermediary_member), [])

    def to_obfuscated_descriptor(self, descriptor):
        """The same descriptor with every class name in the obfuscated namespace of this version."""
        return re.sub(r"L([\w/$]+);", lambda m: "L%s;" % self.intermediary_to_obfuscated.get(m.group(1), m.group(1)), descriptor)

    def to_named_descriptor(self, descriptor, named):
        """The same descriptor with every class name in the Mojang namespace of this version."""
        return re.sub(
            r"L([\w/$]+);",
            lambda m: "L%s;" % named.get(m.group(1), m.group(1)).replace(".", "/"),
            descriptor,
        )


PRIMITIVES = {
    "void": "V", "boolean": "Z", "byte": "B", "char": "C", "short": "S",
    "int": "I", "long": "J", "float": "F", "double": "D",
}

JVM_INHERENT = {
    "values", "valueOf", "toString", "equals", "hashCode", "getClass",
    "clone", "finalize", "wait", "notify", "notifyAll", "compareTo",
}


def source_descriptor(parameters, returns):
    """The JVM descriptor of a member written the way the Mojang mappings write it."""
    if not parameters.strip():
        out = ""
    else:
        out = ""

        for parameter in parameters.split(","):
            parameter = parameter.strip()
            arrays = 0

            while parameter.endswith("[]"):
                parameter = parameter[:-2]
                arrays += 1

            if parameter in PRIMITIVES:
                out += PRIMITIVES[parameter]
            else:
                out += "L%s;" % parameter.replace(".", "/")

            out = "[" * arrays + out

    return "(%s)%s" % (out, PRIMITIVES.get(returns, "L%s;" % returns.replace(".", "/")))


class Official:
    """The Mojang mappings of one version: class names and the constructors of every class."""

    def __init__(self, path):
        self.class_names = {}
        self.constructors = {}
        current = None

        with open(path, encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if "->" not in line:
                    continue

                indented = line.startswith("    ")
                left, right = line.split("->", 1)
                left = left.strip()
                obfuscated = right.strip().rstrip(":").split(" ")[0]

                if not indented:
                    if obfuscated:
                        self.class_names[obfuscated] = left

                    current = left
                    continue

                if current is None or obfuscated != "<init>":
                    continue

                match = re.match(r"^(?:[\d:]+:)?(\S+)\s+<init>\((.*)\)$", left)

                if match:
                    self.constructors.setdefault(current, set()).add(source_descriptor(match.group(2), match.group(1)))


def official_mappings(version, cache):
    """The Mojang mappings of one version, so a rename can be reported next to the intermediary name."""
    path = os.path.join(cache, "mappings", version + ".txt")

    if not os.path.exists(path):
        manifest = json.loads(fetch_bytes(MANIFEST))
        urls = {entry["id"]: entry["url"] for entry in manifest["versions"]}
        meta = json.loads(fetch_bytes(urls[version]))
        download(meta["downloads"]["client_mappings"]["url"], path)

    return Official(path)


def fetch_bytes(url):
    request = urllib.request.Request(url, headers={"User-Agent": "terrainrefreshed-audit"})

    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def download(url, path):
    if os.path.exists(path):
        return path

    os.makedirs(os.path.dirname(path), exist_ok=True)
    print("downloading " + url.rsplit("/", 1)[-1] + " ...", flush=True)

    with open(path, "wb") as handle:
        handle.write(fetch_bytes(url))

    return path


def intermediary_mappings(version, cache):
    path = os.path.join(cache, "intermediary", version + ".jar")

    if not os.path.exists(path):
        download(INTERMEDIARY_MAVEN % (version, version), path)

    return path


def newest_jar(directory):
    jars = [
        os.path.join(directory, name)
        for name in os.listdir(directory)
        if name.endswith(".jar") and "sources" not in name
    ]

    if not jars:
        raise SystemExit("no jar in %s, run the build first" % directory)

    return max(jars, key=os.path.getmtime)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", default=None, help="the built mod jar, newest in build/libs by default")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="directory for the downloaded mappings")
    parser.add_argument("--versions", default=",".join(VERSIONS), help="versions to check")
    args = parser.parse_args()

    versions = [version.strip() for version in args.versions.split(",") if version.strip()]
    jar = args.jar or newest_jar(DEFAULT_JAR)

    classes, refs = scan_jar(jar)
    refmap_classes, refmap_members = scan_refmap(jar)

    print("the jar references %d Minecraft classes and %d members" % (len(classes), len(refs)))
    print("the refmap targets %d classes and %d members" % (len(refmap_classes), len(refmap_members)))

    problems = []
    renames = []

    for version in versions:
        intermediary = Intermediary(intermediary_mappings(version, args.cache))
        official = official_mappings(version, args.cache)
        named_by_intermediary = {
            intermediary_class: official.class_names.get(obfuscated, obfuscated)
            for obfuscated, intermediary_class in intermediary.class_to_intermediary.items()
        }
        moved = 0

        for owner in sorted(classes | refmap_classes):
            if not intermediary.has_class(owner):
                moved += 1
                problems.append((version, owner, owner, "GONE"))
                continue

            named = named_by_intermediary.get(owner, owner)

            if named != owner.replace("/", "."):
                renames.append((version, owner.replace("/", "."), named))

        for owner, member, descriptor, kind in sorted(refs):
            if not intermediary.has_class(owner):
                continue

            if member in JVM_INHERENT:
                continue

            if member == "<init>":
                named_descriptor = intermediary.to_named_descriptor(descriptor, named_by_intermediary)
                named_class = named_by_intermediary.get(owner, owner)
                constructors = official.constructors.get(named_class, set())

                if named_descriptor not in constructors:
                    moved += 1
                    problems.append((version, "%s.%s" % (owner, member), named_descriptor, " ".join(sorted(constructors))))

                continue

            expected = intermediary.to_obfuscated_descriptor(descriptor)
            declared = intermediary.member_descriptors.get(member, set())

            if expected not in declared:
                moved += 1
                problems.append((version, "%s.%s" % (owner, member), descriptor, " ".join(sorted(declared))))

        for descriptor in sorted(refmap_members):
            owner = re.match(r"L([\w/$]+);", descriptor)
            name = re.search(r"(?:method|field)_\d+", descriptor).group(0)

            if not owner or not intermediary.has_class(owner.group(1)):
                moved += 1
                problems.append((version, descriptor, descriptor, "GONE"))
                continue

            expected = intermediary.to_obfuscated_descriptor(descriptor[descriptor.index("("):])
            declared = intermediary.member_descriptors.get(name, set())

            if expected not in declared:
                moved += 1
                problems.append((version, descriptor, descriptor, " ".join(sorted(declared))))

        print("%-8s %d member(s) moved" % (version, moved))

    if renames:
        print("\nMojang names that changed while the intermediary name stayed the same:")

        for version, was, now in renames:
            print("  %-8s %s -> %s" % (version, was, now))

    if problems:
        print("\nmembers whose intermediary name or signature changed:")

        for version, label, was, now in problems:
            print("  %-8s %s: %s -> %s" % (version, label, was, now))

        return 1

    print("\nevery referenced member keeps its intermediary name and signature on all checked versions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
