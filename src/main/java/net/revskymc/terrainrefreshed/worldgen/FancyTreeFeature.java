package net.revskymc.terrainrefreshed.worldgen;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.WorldGenLevel;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.levelgen.feature.Feature;
import net.minecraft.world.level.levelgen.feature.FeaturePlaceContext;

/**
 * A tree grown by one of the {@link TreeForm} silhouettes.
 *
 * The vanilla tree feature builds a straight trunk plus a single foliage blob, which reads as a
 * stick with a pompom. This one asks its form for the logs and leaves, then only takes care of the
 * bookkeeping the game insists on: the trunk and limb blocks go down first, and every leaf keeps
 * the distance value the game computes from the real log positions, so the foliage does not decay
 * away once the tree is generated.
 */
public class FancyTreeFeature extends Feature<FancyTreeConfiguration> {
	private static final int MAX_LEAF_DISTANCE = 7;
	private static final int PLACEMENT_FLAGS = 2;

	public FancyTreeFeature() {
		super(FancyTreeConfiguration.CODEC);
	}

	@Override
	public boolean place(final FeaturePlaceContext<FancyTreeConfiguration> context) {
		FancyTreeConfiguration config = context.config();
		WorldGenLevel level = context.level();
		RandomSource random = context.random();
		BlockPos origin = context.origin();

		int height = config.minHeight() + (config.maxHeight() > config.minHeight()
			? random.nextInt(config.maxHeight() - config.minHeight() + 1)
			: 0);
		int headroom = config.form().spreadsCrown() ? config.canopyRadius() + 2 : 2;

		if (origin.getY() <= level.getMinBuildHeight() || origin.getY() + height + headroom >= level.getMaxBuildHeight()) {
			return false;
		}

		Map<BlockPos, BlockState> logs = new LinkedHashMap<>();
		Map<BlockPos, BlockState> foliage = new HashMap<>();
		config.form().grow(config, random, origin, height, logs, foliage);

		Map<BlockPos, Integer> distances = this.distancesToLogs(logs.keySet(), new HashSet<>(foliage.keySet()));

		for (Map.Entry<BlockPos, BlockState> entry : logs.entrySet()) {
			level.setBlock(entry.getKey(), entry.getValue(), PLACEMENT_FLAGS);
		}

		for (Map.Entry<BlockPos, BlockState> entry : foliage.entrySet()) {
			Integer distance = distances.get(entry.getKey());

			if (distance == null || logs.containsKey(entry.getKey())) {
				continue;
			}

			BlockState state = entry.getValue();

			if (state.hasProperty(BlockStateProperties.DISTANCE)) {
				state = state.setValue(BlockStateProperties.DISTANCE, distance);
			}

			level.setBlock(entry.getKey(), state, PLACEMENT_FLAGS);
		}

		return true;
	}

	private Map<BlockPos, Integer> distancesToLogs(final Iterable<BlockPos> logs, final Set<BlockPos> foliage) {
		Map<BlockPos, Integer> distances = new HashMap<>();
		Deque<BlockPos> queue = new ArrayDeque<>();

		for (BlockPos log : logs) {
			distances.put(log, 0);
			queue.add(log);
		}

		while (!queue.isEmpty()) {
			BlockPos pos = queue.poll();
			int distance = distances.get(pos);

			if (distance >= MAX_LEAF_DISTANCE) {
				continue;
			}

			for (Direction direction : Direction.values()) {
				BlockPos neighbour = pos.relative(direction);

				if (!distances.containsKey(neighbour) && foliage.contains(neighbour)) {
					distances.put(neighbour, distance + 1);
					queue.add(neighbour);
				}
			}
		}

		return distances;
	}
}
