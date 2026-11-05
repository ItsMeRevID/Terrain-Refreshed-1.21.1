package net.revskymc.terrainrefreshed.worldgen;

import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.Mth;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;

/**
 * A meandering stream that cuts a channel into the terrain, lays a bed of gravel and fills the
 * channel with water. The channel follows the local surface height so it flows downhill instead of
 * floating over the landscape.
 */
public class StreamFeature extends Feature<StreamConfiguration> {
	private static final int PLACEMENT_FLAGS = 2;

	public StreamFeature() {
		super(StreamConfiguration.CODEC);
	}

	@Override
	public boolean place(final FeaturePlaceContext<StreamConfiguration> context) {
		StreamConfiguration config = context.config();
		WorldGenLevel level = context.level();
		RandomSource random = context.random();
		BlockPos origin = context.origin();

		int minX = (origin.getX() >> 4) << 4;
		int minZ = (origin.getZ() >> 4) << 4;
		Direction flow = Direction.Plane.HORIZONTAL.getRandomDirection(random);
		Direction bank = flow.getClockWise();
		int x = origin.getX();
		int z = origin.getZ();
		boolean placed = false;

		for (int step = 0; step < config.length(); step++) {
			if (step > 0) {
				if (random.nextFloat() < 0.4F) {
					int drift = random.nextBoolean() ? 1 : -1;
					x += bank.getStepX() * drift;
					z += bank.getStepZ() * drift;
				}

				x += flow.getStepX();
				z += flow.getStepZ();
			}

			x = Mth.clamp(x, minX, minX + 15);
			z = Mth.clamp(z, minZ, minZ + 15);
			placed |= this.carveColumn(config, level, x, z, bank);
		}

		return placed;
	}

	private boolean carveColumn(final StreamConfiguration config, final WorldGenLevel level, final int x, final int z,
		final Direction bank) {
		boolean placed = false;
		int half = (config.width() - 1) / 2;

		for (int offset = -half; offset <= half; offset++) {
			int columnX = x + bank.getStepX() * offset;
			int columnZ = z + bank.getStepZ() * offset;
			int surface = level.getHeight(Heightmap.Types.WORLD_SURFACE_WG, columnX, columnZ);

			if (surface <= level.getMinBuildHeight() + 1 || surface >= level.getMaxBuildHeight()
				|| surface <= level.getSeaLevel()) {
				continue;
			}

			level.setBlock(new BlockPos(columnX, surface - config.depth(), columnZ), config.bed(), PLACEMENT_FLAGS);

			for (int i = 0; i < config.depth(); i++) {
				level.setBlock(new BlockPos(columnX, surface - i, columnZ), config.water(), PLACEMENT_FLAGS);
			}

			placed = true;
		}

		return placed;
	}
}
