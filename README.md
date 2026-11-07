# Terrain Refreshed 1.21.x

![Terrain Refreshed](docs/banner.png)

[![Latest release](https://img.shields.io/github/v/release/ItsMeRevID/Terrain-Refreshed-1.21.1?label=release)](https://github.com/ItsMeRevID/Terrain-Refreshed-1.21.1/releases/latest)
[![Build](https://github.com/ItsMeRevID/Terrain-Refreshed-1.21.1/actions/workflows/build.yml/badge.svg)](https://github.com/ItsMeRevID/Terrain-Refreshed-1.21.1/actions/workflows/build.yml)

The Minecraft 1.21 line of Terrain Refreshed: a Fabric mod that overhauls world generation with
realistic terrain shaping, dramatic mountains, flowing streams and rivers, 100 new biomes with
hand-tuned colours, natural vegetation and organically grown fancy trees.

The build for Minecraft 26.3 lives in [ItsMeRevID/Terrain-Refreshed](https://github.com/ItsMeRevID/Terrain-Refreshed).

| | |
|---|---|
| Author | RevSkyMC |
| Package | `net.revskymc.terrainrefreshed` |
| Minecraft | 1.21.1 - 1.21.11 |
| Loader | Fabric 0.20.1 |
| Fabric API | 0.116.17+1.21.1 |
| Java | 21 |
| License | MIT |

## Features

- **Realistic terrain shape** — the overworld cheese density is replaced with a blended field of
  river carving, mountain lift, crag detail and rolling relief, so valleys, plateaus and ridges
  replace the vanilla hills.
- **Fancy mountains** — mountain height is masked against the continentalness and ridge noise, so
  ranges grow tall and craggy only where the terrain calls for them.
- **Streams** — a dedicated `terrainrefreshed:stream` feature carves a meandering channel into the
  surface, lays a gravel bed and fills it with water; the river density function carves the wider
  valleys the streams run through.
- **100 new biomes** — a full biome set with their own climate cells, grass/foliage/water colours
  and vegetation profiles. The biomes are injected into the overworld multi-noise source at runtime,
  so they replace the vanilla biomes of their climate cells instead of being appended to them.
- **Fancy biome colours** — every biome carries its own water, grass, foliage and dry-foliage
  tints, plus a sky colour attribute.
- **Natural vegetation** — ground cover, flowers, mushrooms, sugar cane, vines and lily pads are
  layered per biome family (meadow, forest, wetland, arid, rock, jungle, savanna).
- **Fancy trees** — `terrainrefreshed:fancy_tree` is one feature with nine silhouettes in
  `worldgen/TreeForm.java`, each built the way the real tree grows: `spreading` (leaning trunk,
  sideways limbs, blobby canopy), `conical` spruce whose whorls shorten as they climb, `pine` tiers
  upturned along a bare shaft, `weeping` willow curtains, `floral` tabebuya as one blossom dome on
  a clear stem, `umbrella` acacia flattened into a disc, `columnar` cypress that never widens,
  `baobab` with a four-log barrel and stubby arms, and `palm` with a leaning stem and eight drooping
  fronds. Eleven species use them: oak, birch, jungle (spreading), spruce (conical), pine, willow,
  acacia (umbrella), tabebuya (cherry blocks), cypress, baobab and palm.

## Running on 1.21.2 and later

The biome data was authored against the 1.21.1 schema, and the releases after it moved that schema
around: the carver, music and attribute fields of a biome changed, and the patch feature that
replaces sugar cane was swapped for the one that replaces pumpkin. A datapack that does not match
the schema of the running game is rejected outright, and the mod then loads with every one of its
biomes unbound.

`compat/BiomeJsonAdapter` therefore reshapes each biome for the release that is actually running,
before the registry reads it:

- the fields that were added or renamed after 1.21.1 are removed or filled in with the value the
  running game expects,
- `minecraft:patch_sugar_cane` and `minecraft:patch_pumpkin` are swapped on the releases from
  1.21.5 onwards, where vanilla flipped them.

`compat/BiomeSchema` holds the table that says which release is running and what it expects.

## Layout

```
src/main/java/net/revskymc/terrainrefreshed/
  TerrainRefreshed.java          mod entrypoint, feature type registration
  compat/
    BiomeSchema.java             what each 1.21.x release expects of a biome file
    BiomeJsonAdapter.java        reshapes the biome files for the running release
  mixin/
    MultiNoiseBiomeSourceParameterListMixin.java  runtime injection into the overworld biome source
    RegistryDataLoaderMixin.java  reshapes the biome files before the registry binds them
  worldgen/
    FancyTreeFeature.java        custom tree feature
    FancyTreeConfiguration.java  its configuration codec
    TreeForm.java                the nine tree silhouettes the feature grows
    StreamFeature.java           custom stream feature
    StreamConfiguration.java     its configuration codec
    OverworldBiomeExtender.java  carves the mod's climate cells out of the vanilla biome list
    BiomeClimateTable.java       generated climate table
src/main/resources/data/terrainrefreshed/worldgen/  biomes, configured features, noises, density functions
src/main/resources/data/minecraft/worldgen/density_function/  overworld terrain overrides
src/main/resources/assets/terrainrefreshed/icon.png  mod icon, referenced by fabric.mod.json
docs/banner.png  page banner for the mod hosts
tools/convert_from_26_3.py       rebuilds this port's content from the 26.3 project
tools/check_feature_cycles.py    offline check for the game's feature order cycle check
tools/climate_audit.py           offline check of the climate volume each cell keeps
tools/smoke_density.py           searches biomes from several origins to measure real rarity
tools/smoke_leaves.py            checks that no placed leaf sits in the state the game rots
tools/smoke_trees.py             plants each species in the air and measures its silhouette
tools/smoke_test.sh              dedicated server smoke test driven over RCON
```

## Building

```bash
./gradlew build
```

The runnable jar is written to `build/libs/`.

## Smoke test

`tools/smoke_test.sh` boots the dev dedicated server, waits for the world to generate, then checks
over RCON that every new biome is reachable with `/locate biome`, that the custom tree and stream
features place successfully, and — with `tools/smoke_trees.py` — that each species actually grows the
silhouette its form is named after.

`tools/smoke_leaves.py` is the separate gate for the foliage: it plants every species, counts the
leaves the game placed, and then counts the ones sitting in the state the game rots them in. A leaf
rots when it is not persistent and its distance to the nearest log has reached seven, so the gate
asserts that no leaf of any species is in that state.

```bash
bash tools/smoke_test.sh smoke                                  # full locate sweep
python tools/smoke_leaves.py 127.0.0.1 25575 <rcon-password>    # leaf gate against a running server
```

## Releases

Every push to `main` is rebuilt by GitHub Actions, so the repository always carries the current
build. To ship a new version, change `version=` in `gradle.properties` and push: the tag, the
release title and the attached jar follow that file.

| Workflow | What it does |
|---|---|
| `build.yml` | builds the mod on every push and pull request and stores the jars as a workflow artifact |
| `release.yml` | builds on `main`, then creates or refreshes the release of the current version and replaces the attached jar |
| `modrinth.yml` | uploads the jar to Modrinth; the release workflow dispatches it right after the GitHub release is published |

The jar of the newest build is always at
<https://github.com/ItsMeRevID/Terrain-Refreshed-1.21.1/releases/latest>.

Publishing on Modrinth needs three things, once:

1. create the project page for this 1.21.x build
2. create an access token with the `write:versions` scope
3. add the token as the repository secret `MODRINTH_TOKEN` and the project slug as the
   repository variable `MODRINTH_PROJECT_ID`

Until the token is there, the Modrinth workflow reports that it skipped and the rest of the
pipeline stays green. `MODRINTH_GAME_VERSIONS` overrides the Minecraft versions the release
claims and defaults to the whole 1.21.1 - 1.21.11 range.

## License

MIT — see [LICENSE](LICENSE).
