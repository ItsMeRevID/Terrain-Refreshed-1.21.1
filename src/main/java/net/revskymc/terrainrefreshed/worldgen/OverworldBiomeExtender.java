package net.revskymc.terrainrefreshed.worldgen;

import com.mojang.datafixers.util.Pair;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderGetter;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Climate;
import net.revskymc.terrainrefreshed.TerrainRefreshed;

/**
 * Cuts the Terrain Refreshed climate cells out of the vanilla overworld biome list.
 *
 * <p>Vanilla picks the biome with the lowest climate fitness, so a new biome that merely shares a
 * cell with a vanilla one loses the tie on tree traversal order. Removing the overlapping volume
 * from the vanilla points leaves the new biome as the only one with zero distance inside its cell.
 */
public final class OverworldBiomeExtender {
	private static final int DIMENSIONS = 5;
	private static final long SURFACE_DEPTH = 0L;
	private static final long DEEP_SURFACE_DEPTH = 10000L;

	private OverworldBiomeExtender() {}

	public static Climate.ParameterList<Holder<Biome>> extend(
		final Climate.ParameterList<Holder<Biome>> vanilla,
		final HolderGetter<Biome> biomes
	) {
		List<Cell> cells = new ArrayList<>();

		for (BiomeClimateTable.Entry entry : BiomeClimateTable.entries()) {
			biomes.get(entry.biome()).ifPresent(holder -> cells.add(new Cell(Box.of(entry), holder)));
		}

		if (cells.isEmpty()) {
			return vanilla;
		}

		List<Pair<Climate.ParameterPoint, Holder<Biome>>> extended = new ArrayList<>();

		for (Pair<Climate.ParameterPoint, Holder<Biome>> entry : vanilla.values()) {
			Climate.ParameterPoint point = entry.getFirst();

			if (!isSurface(point.depth())) {
				extended.add(entry);
				continue;
			}

			List<Box> pieces = new ArrayList<>();
			pieces.add(Box.of(point));

			for (Cell cell : cells) {
				pieces = subtract(pieces, cell.box);
			}

			for (Box piece : pieces) {
				extended.add(Pair.of(piece.toPoint(point.depth(), point.offset()), entry.getSecond()));
			}
		}

		for (Cell cell : cells) {
			extended.add(Pair.of(cell.box.toPoint(Climate.Parameter.point(0.0F), 0L), cell.holder));
			extended.add(Pair.of(cell.box.toPoint(Climate.Parameter.point(1.0F), 0L), cell.holder));
		}

		Climate.ParameterList<Holder<Biome>> result = new Climate.ParameterList<>(extended);

		TerrainRefreshed.LOGGER.info(
			"Extended overworld climate list from {} to {} entries", vanilla.values().size(), extended.size()
		);

		verify(result, cells);

		return result;
	}

	/**
	 * Resolves the centre of every Terrain Refreshed cell back through the finished list. A cell that
	 * a vanilla point still shadows would be invisible in the world, so this catches it at load time
	 * instead of leaving a biome that never shows up.
	 *
	 * <p>Both surface depths are checked because every cell is emitted twice, once for the surface
	 * layer and once for the layer below it.
	 */
	private static void verify(
		final Climate.ParameterList<Holder<Biome>> list,
		final List<Cell> cells
	) {
		int matched = 0;

		for (Cell cell : cells) {
			long[] center = cell.box.center();

			if (resolves(list, cell, center, SURFACE_DEPTH) && resolves(list, cell, center, DEEP_SURFACE_DEPTH)) {
				matched++;
			} else {
				TerrainRefreshed.LOGGER.warn("Climate cell {} is shadowed by another biome", name(cell.holder));
			}
		}

		TerrainRefreshed.LOGGER.info("Verified {} of {} Terrain Refreshed climate cells", matched, cells.size());
	}

	/**
	 * The five centre coordinates are the quantised climate axes in {@link Box} order, which differs
	 * from {@link Climate.TargetPoint} order only in that depth sits between erosion and weirdness.
	 */
	private static boolean resolves(
		final Climate.ParameterList<Holder<Biome>> list,
		final Cell cell,
		final long[] center,
		final long depth
	) {
		Holder<Biome> resolved = list.findValue(
			new Climate.TargetPoint(center[0], center[1], center[2], center[3], depth, center[4])
		);

		return resolved.is(cell.holder);
	}

	private static String name(final Holder<Biome> holder) {
		return holder.unwrapKey().map(key -> key.location().toString()).orElse("<unregistered>");
	}

	private static boolean isSurface(final Climate.Parameter depth) {
		return depth.min() == depth.max() && (depth.min() == SURFACE_DEPTH || depth.min() == DEEP_SURFACE_DEPTH);
	}

	private static List<Box> subtract(final List<Box> pieces, final Box cutter) {
		List<Box> result = new ArrayList<>();

		for (Box piece : pieces) {
			if (isDisjoint(piece, cutter)) {
				result.add(piece);
			} else {
				result.addAll(split(piece, cutter, 0));
			}
		}

		return result;
	}

	/**
	 * A cutter that misses the box in any single dimension cannot touch it at all. Checking this up
	 * front keeps disjoint cutters from splitting the box in the dimensions that do overlap.
	 */
	private static boolean isDisjoint(final Box box, final Box cutter) {
		for (int dimension = 0; dimension < DIMENSIONS; dimension++) {
			if (box.max[dimension] <= cutter.min[dimension] || cutter.max[dimension] <= box.min[dimension]) {
				return true;
			}
		}

		return false;
	}

	private static List<Box> split(final Box box, final Box cutter, final int dimension) {
		if (dimension == DIMENSIONS) {
			return List.of();
		}

		List<Box> result = new ArrayList<>();

		if (box.min[dimension] < cutter.min[dimension]) {
			result.add(box.with(dimension, box.min[dimension], cutter.min[dimension] - 1L));
		}

		if (box.max[dimension] > cutter.max[dimension]) {
			result.add(box.with(dimension, cutter.max[dimension] + 1L, box.max[dimension]));
		}

		long midMin = Math.max(box.min[dimension], cutter.min[dimension]);
		long midMax = Math.min(box.max[dimension], cutter.max[dimension]);
		result.addAll(split(box.with(dimension, midMin, midMax), cutter, dimension + 1));

		return result;
	}

	private record Cell(Box box, Holder<Biome> holder) {}

	private static final class Box {
		private final long[] min;
		private final long[] max;

		private Box(final long[] min, final long[] max) {
			this.min = min;
			this.max = max;
		}

		static Box of(final Climate.ParameterPoint point) {
			return new Box(
				new long[] {
					point.temperature().min(),
					point.humidity().min(),
					point.continentalness().min(),
					point.erosion().min(),
					point.weirdness().min()
				},
				new long[] {
					point.temperature().max(),
					point.humidity().max(),
					point.continentalness().max(),
					point.erosion().max(),
					point.weirdness().max()
				}
			);
		}

		static Box of(final BiomeClimateTable.Entry entry) {
			return new Box(
				new long[] {
					entry.temperature().min(),
					entry.humidity().min(),
					entry.continentalness().min(),
					entry.erosion().min(),
					entry.weirdness().min()
				},
				new long[] {
					entry.temperature().max(),
					entry.humidity().max(),
					entry.continentalness().max(),
					entry.erosion().max(),
					entry.weirdness().max()
				}
			);
		}

		Box with(final int dimension, final long newMin, final long newMax) {
			long[] clippedMin = this.min.clone();
			long[] clippedMax = this.max.clone();
			clippedMin[dimension] = newMin;
			clippedMax[dimension] = newMax;
			return new Box(clippedMin, clippedMax);
		}

		/**
		 * A point that lies inside the box on every axis, so it belongs to the box however the edges
		 * are treated.
		 */
		long[] center() {
			long[] center = new long[DIMENSIONS];

			for (int dimension = 0; dimension < DIMENSIONS; dimension++) {
				center[dimension] = this.min[dimension] + (this.max[dimension] - this.min[dimension]) / 2L;
			}

			return center;
		}

		Climate.ParameterPoint toPoint(final Climate.Parameter depth, final long offset) {
			return new Climate.ParameterPoint(
				new Climate.Parameter(this.min[0], this.max[0]),
				new Climate.Parameter(this.min[1], this.max[1]),
				new Climate.Parameter(this.min[2], this.max[2]),
				new Climate.Parameter(this.min[3], this.max[3]),
				depth,
				new Climate.Parameter(this.min[4], this.max[4]),
				offset
			);
		}
	}
}
