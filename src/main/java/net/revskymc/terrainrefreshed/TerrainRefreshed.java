package net.revskymc.terrainrefreshed;

import net.fabricmc.api.ModInitializer;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.revskymc.terrainrefreshed.worldgen.FancyTreeFeature;
import net.revskymc.terrainrefreshed.worldgen.StreamFeature;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public class TerrainRefreshed implements ModInitializer {
	public static final String MOD_ID = "terrainrefreshed";
	public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);

	@Override
	public void onInitialize() {
		Registry.register(
			BuiltInRegistries.FEATURE,
			ResourceLocation.fromNamespaceAndPath(MOD_ID, "fancy_tree"),
			new FancyTreeFeature()
		);
		Registry.register(
			BuiltInRegistries.FEATURE,
			ResourceLocation.fromNamespaceAndPath(MOD_ID, "stream"),
			new StreamFeature()
		);

		LOGGER.info("Terrain Refreshed initializing");
	}
}
