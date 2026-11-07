package net.revskymc.terrainrefreshed.compat;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

import net.fabricmc.loader.api.FabricLoader;
import net.revskymc.terrainrefreshed.TerrainRefreshed;

/**
 * The biome definition schema changed several times during the 1.21.x line, so the mod ships the
 * 1.21.1 layout and rewrites the definitions in memory when a newer game expects a different one.
 */
public enum BiomeSchema {
	/** 1.21.1: {@code carvers} maps a generation step to carver ids, {@code music} is a single track. */
	V1_21_1(1),
	/** 1.21.2 - 1.21.3: {@code carvers} is a flat list of carver ids. */
	V1_21_2(2),
	/** 1.21.4 - 1.21.10: {@code music} is a weighted list of tracks. */
	V1_21_4(4),
	/** 1.21.11+: effect colours are hex strings and the sky, fog and audio data live in {@code attributes}. */
	V1_21_11(11);

	private static final Pattern VERSION = Pattern.compile("(\\d+)\\.(\\d+)(?:\\.(\\d+))?");

	/** The 1.21.x patch number of the running game, 0 when the version cannot be read. */
	private static final int GAME_PATCH = detectPatch();

	private static final BiomeSchema CURRENT = detect(GAME_PATCH);

	private final int patch;

	BiomeSchema(final int patch) {
		this.patch = patch;
	}

	public static BiomeSchema current() {
		return CURRENT;
	}

	/**
	 * The 1.21.x patch number of the running game. Some changes only affect a single patch and are
	 * therefore not part of a schema tier.
	 */
	public static int gamePatch() {
		return GAME_PATCH;
	}

	public int patch() {
		return this.patch;
	}

	private static BiomeSchema detect(final int patch) {
		if (patch <= 1) {
			return V1_21_1;
		}

		if (patch <= 3) {
			return V1_21_2;
		}

		return patch >= 11 ? V1_21_11 : V1_21_4;
	}

	private static int detectPatch() {
		final String version = minecraftVersion();
		final Matcher matcher = VERSION.matcher(version);

		if (!matcher.find()) {
			TerrainRefreshed.LOGGER.warn("Could not read the Minecraft version '{}', keeping the 1.21.1 biome schema", version);
			return 0;
		}

		final int minor = Integer.parseInt(matcher.group(2));
		final int patch = matcher.group(3) == null ? 0 : Integer.parseInt(matcher.group(3));

		if (minor != 21) {
			TerrainRefreshed.LOGGER.warn("Minecraft {} is outside the supported 1.21.x range, keeping the 1.21.1 biome schema", version);
			return 0;
		}

		return patch;
	}

	private static String minecraftVersion() {
		return FabricLoader.getInstance()
			.getModContainer("minecraft")
			.map(container -> container.getMetadata().getVersion().getFriendlyString())
			.orElse("1.21.1");
	}
}
