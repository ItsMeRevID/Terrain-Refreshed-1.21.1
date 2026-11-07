package net.revskymc.terrainrefreshed.compat;

import java.util.Map;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;

/**
 * Rewrites a biome definition that was written for 1.21.1 into the layout the running game
 * expects. Only definitions that actually look like biomes are touched.
 */
public final class BiomeJsonAdapter {
	private static final String SKY_COLOR = "minecraft:visual/sky_color";
	private static final String FOG_COLOR = "minecraft:visual/fog_color";
	private static final String WATER_FOG_COLOR = "minecraft:visual/water_fog_color";
	private static final String AMBIENT_SOUNDS = "minecraft:audio/ambient_sounds";
	private static final String BACKGROUND_MUSIC = "minecraft:audio/background_music";
	private static final String MOD_NAMESPACE = "terrainrefreshed:";
	private static final String SUGAR_CANE_PATCH = "minecraft:patch_sugar_cane";
	private static final String PUMPKIN_PATCH = "minecraft:patch_pumpkin";

	/** 1.21.5 is the patch that swapped the sugar cane and the pumpkin patch. */
	private static final int FEATURE_ORDER_PATCH = 5;

	private BiomeJsonAdapter() {
	}

	public static JsonElement adapt(final JsonElement json, final BiomeSchema schema) {
		if (schema == BiomeSchema.V1_21_1 || json == null || !json.isJsonObject()) {
			return json;
		}

		final JsonObject root = json.getAsJsonObject();

		if (!isBiome(root)) {
			return json;
		}

		flattenCarvers(root);

		if (schema == BiomeSchema.V1_21_4) {
			weightMusic(root);
		}

		if (schema == BiomeSchema.V1_21_11) {
			convertEffects(root);
		}

		if (BiomeSchema.gamePatch() >= FEATURE_ORDER_PATCH) {
			alignFeatureOrder(root);
		}

		return json;
	}

	private static boolean isBiome(final JsonObject root) {
		return root.has("features") && root.has("spawners") && root.has("carvers");
	}

	/** 1.21.1 groups the carvers per generation step, every later version wants a flat list. */
	private static void flattenCarvers(final JsonObject root) {
		final JsonElement carvers = root.get("carvers");

		if (carvers == null || !carvers.isJsonObject()) {
			return;
		}

		final JsonArray flattened = new JsonArray();

		for (final Map.Entry<String, JsonElement> step : carvers.getAsJsonObject().entrySet()) {
			final JsonElement value = step.getValue();

			if (value.isJsonArray()) {
				value.getAsJsonArray().forEach(flattened::add);
			} else {
				flattened.add(value);
			}
		}

		root.add("carvers", flattened);
	}

	/** 1.21.4 turned the single background track into a weighted list of tracks. */
	private static void weightMusic(final JsonObject root) {
		final JsonElement effects = root.get("effects");

		if (effects == null || !effects.isJsonObject()) {
			return;
		}

		final JsonObject effectObject = effects.getAsJsonObject();
		final JsonElement music = effectObject.get("music");

		if (music == null || !music.isJsonObject()) {
			return;
		}

		final JsonObject track = new JsonObject();
		track.add("data", music);
		track.add("weight", new JsonPrimitive(1));

		final JsonArray tracks = new JsonArray();
		tracks.add(track);

		effectObject.add("music", tracks);
	}

	/** 1.21.11 turned the effect colours into hex strings and moved the sky, fog and audio data out. */
	private static void convertEffects(final JsonObject root) {
		final JsonElement effects = root.get("effects");

		if (effects == null || !effects.isJsonObject()) {
			return;
		}

		final JsonObject effectObject = effects.getAsJsonObject();
		final JsonObject attributes = root.has("attributes") && root.get("attributes").isJsonObject()
			? root.getAsJsonObject("attributes")
			: new JsonObject();

		toHex(effectObject, "water_color");
		toHex(effectObject, "foliage_color");
		toHex(effectObject, "grass_color");
		toHex(effectObject, "dry_foliage_color");

		moveToAttribute(effectObject, attributes, "sky_color", SKY_COLOR);
		moveToAttribute(effectObject, attributes, "fog_color", FOG_COLOR);
		moveToAttribute(effectObject, attributes, "water_fog_color", WATER_FOG_COLOR);

		final JsonElement mood = effectObject.remove("mood_sound");

		if (mood != null && mood.isJsonObject()) {
			final JsonObject ambient = attributes.has(AMBIENT_SOUNDS) && attributes.get(AMBIENT_SOUNDS).isJsonObject()
				? attributes.getAsJsonObject(AMBIENT_SOUNDS)
				: new JsonObject();
			ambient.add("mood", mood);
			attributes.add(AMBIENT_SOUNDS, ambient);
		}

		final JsonElement music = effectObject.remove("music");

		if (music != null && music.isJsonObject()) {
			final JsonObject background = new JsonObject();
			background.add("default", music);
			attributes.add(BACKGROUND_MUSIC, background);
		}

		root.add("attributes", attributes);
	}

	private static void toHex(final JsonObject effects, final String key) {
		final JsonElement colour = effects.get(key);

		if (colour == null || !colour.isJsonPrimitive() || !colour.getAsJsonPrimitive().isNumber()) {
			return;
		}

		effects.add(key, new JsonPrimitive(String.format("#%06x", colour.getAsInt() & 0xFFFFFF)));
	}

	private static void moveToAttribute(final JsonObject effects, final JsonObject attributes, final String key, final String attribute) {
		final JsonElement colour = effects.remove(key);

		if (colour == null || !colour.isJsonPrimitive() || !colour.getAsJsonPrimitive().isNumber()) {
			return;
		}

		attributes.add(attribute, new JsonPrimitive(String.format("#%06x", colour.getAsInt() & 0xFFFFFF)));
	}

	/**
	 * The game chains the features of every biome into one graph and refuses to start when two
	 * biomes order the same features differently. 1.21.5 moved the pumpkin patch in front of the
	 * sugar cane patch, so the shipped 1.21.1 order has to be swapped for the newer layout.
	 */
	private static void alignFeatureOrder(final JsonObject root) {
		if (!isModBiome(root)) {
			return;
		}

		final JsonElement features = root.get("features");

		if (features == null || !features.isJsonArray()) {
			return;
		}

		for (final JsonElement step : features.getAsJsonArray()) {
			if (!step.isJsonArray()) {
				continue;
			}

			final JsonArray list = step.getAsJsonArray();
			final int cane = indexOf(list, SUGAR_CANE_PATCH);
			final int pumpkin = indexOf(list, PUMPKIN_PATCH);

			if (cane < 0 || pumpkin < 0 || cane > pumpkin) {
				continue;
			}

			list.set(cane, new JsonPrimitive(PUMPKIN_PATCH));
			list.set(pumpkin, new JsonPrimitive(SUGAR_CANE_PATCH));
		}
	}

	private static boolean isModBiome(final JsonObject root) {
		final JsonElement features = root.get("features");

		if (features == null || !features.isJsonArray()) {
			return false;
		}

		for (final JsonElement step : features.getAsJsonArray()) {
			if (!step.isJsonArray()) {
				continue;
			}

			for (final JsonElement feature : step.getAsJsonArray()) {
				if (feature.isJsonPrimitive() && feature.getAsString().startsWith(MOD_NAMESPACE)) {
					return true;
				}
			}
		}

		return false;
	}

	private static int indexOf(final JsonArray list, final String feature) {
		for (int index = 0; index < list.size(); index++) {
			final JsonElement element = list.get(index);

			if (element.isJsonPrimitive() && feature.equals(element.getAsString())) {
				return index;
			}
		}

		return -1;
	}
}
