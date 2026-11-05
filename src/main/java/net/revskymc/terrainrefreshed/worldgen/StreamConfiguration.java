package net.revskymc.terrainrefreshed.worldgen;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.feature.configurations.FeatureConfiguration;

/** How long, wide and deep a {@link StreamFeature} channel is and what it is filled with. */
public record StreamConfiguration(
	int length,
	int width,
	int depth,
	BlockState water,
	BlockState bed
) implements FeatureConfiguration {
	public static final Codec<StreamConfiguration> CODEC = RecordCodecBuilder.create(
		i -> i.group(
				Codec.intRange(2, 64).fieldOf("length").forGetter(StreamConfiguration::length),
				Codec.intRange(1, 8).fieldOf("width").forGetter(StreamConfiguration::width),
				Codec.intRange(1, 4).fieldOf("depth").forGetter(StreamConfiguration::depth),
				BlockState.CODEC.fieldOf("water").forGetter(StreamConfiguration::water),
				BlockState.CODEC.fieldOf("bed").forGetter(StreamConfiguration::bed)
			)
			.apply(i, StreamConfiguration::new)
	);
}
