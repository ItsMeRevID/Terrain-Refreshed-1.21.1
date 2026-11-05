package net.revskymc.terrainrefreshed.worldgen;

import com.mojang.serialization.Codec;
import com.mojang.serialization.codecs.RecordCodecBuilder;
import java.util.Locale;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.feature.configurations.FeatureConfiguration;

/**
 * What a {@link FancyTreeFeature} is told to grow: two blocks, a silhouette from {@link TreeForm}
 * and the size the form has to work within.
 */
public record FancyTreeConfiguration(
	BlockState trunk,
	BlockState leaves,
	TreeForm form,
	int minHeight,
	int maxHeight,
	int canopyRadius,
	float branchChance
) implements FeatureConfiguration {
	public static final Codec<FancyTreeConfiguration> CODEC = RecordCodecBuilder.create(
		i -> i.group(
				BlockState.CODEC.fieldOf("trunk").forGetter(FancyTreeConfiguration::trunk),
				BlockState.CODEC.fieldOf("leaves").forGetter(FancyTreeConfiguration::leaves),
				Codec.STRING.xmap(TreeForm::byName, form -> form.name().toLowerCase(Locale.ROOT))
					.fieldOf("form").forGetter(FancyTreeConfiguration::form),
				Codec.intRange(2, 64).fieldOf("min_height").forGetter(FancyTreeConfiguration::minHeight),
				Codec.intRange(2, 64).fieldOf("max_height").forGetter(FancyTreeConfiguration::maxHeight),
				Codec.intRange(1, 12).fieldOf("canopy_radius").forGetter(FancyTreeConfiguration::canopyRadius),
				Codec.floatRange(0.0F, 1.0F).fieldOf("branch_chance").forGetter(FancyTreeConfiguration::branchChance)
			)
			.apply(i, FancyTreeConfiguration::new)
	);
}
