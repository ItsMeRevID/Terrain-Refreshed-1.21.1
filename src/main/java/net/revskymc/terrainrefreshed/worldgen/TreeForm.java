package net.revskymc.terrainrefreshed.worldgen;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;

/**
 * The silhouette a tree species grows into.
 *
 * One trunk-and-blob routine cannot read as a spruce and as a willow at the same time, so every
 * species picks one of these forms and the form decides where the limbs go and how the foliage
 * follows them. The forms are drawn from the real trees they are named after: a spruce cone ringed
 * by whorls that shorten as they climb, a pine that spends most of its height as bare trunk and
 * only carries tiers near the crown, a willow whose limbs drop curtains of leaves, a tabebuya that
 * tops a slim trunk with one rounded blossom dome, a savanna acacia flattened into a disc, a
 * cypress grown as a column, a baobab as a thick barrel with stubby arms and a palm as a leaning
 * shaft with a star of fronds.
 */
public enum TreeForm {
	/** The generic broadleaf: a leaning trunk, limbs off the upper half, blobby canopy. */
	SPREADING {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			List<BlockPos> spine = spine(random, origin, height, 0.6F);
			trunk(logs, tree.trunk(), spine);

			int first = Math.max(2, height / 2);
			int last = height - 2;

			for (int level = first; level <= last; level++) {
				if (random.nextFloat() > tree.branchChance()) {
					continue;
				}

				Direction direction = Direction.Plane.HORIZONTAL.getRandomDirection(random);
				int length = 1 + random.nextInt(3);
				BlockPos base = spine.get(level);
				limb(logs, tree.trunk(), base, direction, length, 0);
				blob(foliage, tree.leaves(), offset(base, direction, length, length, 0), 1 + random.nextInt(2));
			}

			BlockPos top = spine.get(height - 1);
			int radius = tree.canopyRadius();
			ellipsoid(foliage, tree.leaves(), top, radius, Math.max(1, radius / 2 + 1), 1.0F, random);

			int crown = Math.max(1, height / 4);

			for (int i = 1; i <= crown; i++) {
				blob(foliage, tree.leaves(), spine.get(height - 1 - i), Math.max(1, radius - i));
			}
		}
	},
	/** Spruce and fir: a straight spire ringed by whorls that get shorter as they climb. */
	CONICAL {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			List<BlockPos> spine = spine(random, origin, height, 0.0F);
			trunk(logs, tree.trunk(), spine);

			int first = 2;
			int last = height - 2;
			Direction[] ring = shuffled(random);

			for (int level = first; level <= last; level++) {
				if (random.nextFloat() > 0.55F + tree.branchChance() * 0.45F) {
					continue;
				}

				float climb = (level - first) / (float) Math.max(1, last - first);
				int length = Math.max(1, Math.round(tree.canopyRadius() * (1.15F - climb)));
				int rise = -Math.min(1, length / 3);
				BlockPos base = spine.get(level);

				for (int i = 0; i < ring.length; i++) {
					Direction direction = ring[(i + level) % ring.length];
					BlockPos tip = limb(logs, tree.trunk(), base, direction, length, rise);

					for (int step = 1; step < length; step++) {
						if (random.nextFloat() < 0.55F) {
							foliage.putIfAbsent(offset(base, direction, step, length, rise).above().immutable(), tree.leaves());
						}
					}

					blob(foliage, tree.leaves(), tip, 1);
				}
			}

			blob(foliage, tree.leaves(), spine.get(height - 1), 1);
		}
	},
	/** Pine: most of the trunk stays bare, the foliage sits in a few upturned tiers under the crown. */
	PINE {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			List<BlockPos> spine = spine(random, origin, height, 0.0F);
			trunk(logs, tree.trunk(), spine);

			int tiers = 3 + random.nextInt(3);
			int spacing = Math.max(1, height / (tiers + 2));

			for (int tier = 0; tier < tiers; tier++) {
				int level = height - 2 - tier * spacing;

				if (level < 2) {
					break;
				}

				int length = Math.max(1, tree.canopyRadius() - tier / 2 + random.nextInt(2));

				for (Direction direction : shuffled(random)) {
					if (random.nextFloat() > tree.branchChance()) {
						continue;
					}

					BlockPos tip = limb(logs, tree.trunk(), spine.get(level), direction, length, 2);
					ellipsoid(foliage, tree.leaves(), tip, 1 + random.nextInt(2), 1, 1.2F, random);
				}
			}

			ellipsoid(foliage, tree.leaves(), spine.get(height - 1), tree.canopyRadius() / 2 + 1, 1, 1.2F, random);
		}
	},
	/** Willow: arching limbs and a crown that both drop long curtains of leaves. */
	WEEPING {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			List<BlockPos> spine = spine(random, origin, height, 0.35F);
			trunk(logs, tree.trunk(), spine);

			BlockPos top = spine.get(height - 1);
			int radius = tree.canopyRadius();
			int vertical = Math.max(1, radius / 2 + 1);
			ellipsoid(foliage, tree.leaves(), top, radius, vertical, 1.0F, random);

			for (int dx = -radius; dx <= radius; dx++) {
				for (int dz = -radius; dz <= radius; dz++) {
					double offset = Math.sqrt(dx * dx + dz * dz);

					if (offset < radius - 0.5 || random.nextFloat() > tree.branchChance()) {
						continue;
					}

					curtain(foliage, tree.leaves(), top.offset(dx, -vertical, dz), 2 + random.nextInt(radius + 2), random);
				}
			}

			for (int level = height / 2; level < height - 1; level++) {
				if (random.nextFloat() > tree.branchChance()) {
					continue;
				}

				Direction direction = Direction.Plane.HORIZONTAL.getRandomDirection(random);
				int length = 2 + random.nextInt(radius);
				BlockPos base = spine.get(level);
				curtain(foliage, tree.leaves(), limb(logs, tree.trunk(), base, direction, length, 1),
					3 + random.nextInt(radius + 3), random);
			}
		}
	},
	/** Tabebuya and other blossom trees: a slim bare trunk under one rounded dome of flowers. */
	FLORAL {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			List<BlockPos> spine = spine(random, origin, height, 0.0F);
			trunk(logs, tree.trunk(), spine);

			BlockPos top = spine.get(height - 1);
			int radius = tree.canopyRadius();
			ellipsoid(foliage, tree.leaves(), top.above(), radius, Math.max(2, radius * 3 / 4),
				0.85F + tree.branchChance() * 0.3F, random);

			for (int i = 0; i < 3; i++) {
				Direction direction = Direction.Plane.HORIZONTAL.getRandomDirection(random);
				int reach = Math.max(1, radius / 2);
				blob(foliage, tree.leaves(), offset(top, direction, reach, reach, -1), reach);
			}
		}
	},
	/** Savanna acacia: the trunk forks near the top and the crown is a flat wide disc. */
	UMBRELLA {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			List<BlockPos> spine = spine(random, origin, height, 0.0F);
			int fork = Math.max(2, height * 3 / 5);
			trunk(logs, tree.trunk(), spine.subList(0, fork + 1));

			BlockPos base = spine.get(fork);
			int rise = height - 1 - fork;
			int reach = Math.max(1, tree.canopyRadius() - 1);
			Direction[] ring = shuffled(random);

			for (int i = 0; i < 3; i++) {
				limb(logs, tree.trunk(), base, ring[i], reach, rise);
			}

			disc(foliage, tree.leaves(), spine.get(height - 1), tree.canopyRadius() + 1, tree.branchChance(), random);
		}
	},
	/** Cypress and poplar: foliage hugs the trunk from the middle of the tree to the tip. */
	COLUMNAR {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			List<BlockPos> spine = spine(random, origin, height, 0.0F);
			trunk(logs, tree.trunk(), spine);

			int first = height * 2 / 5;
			int middle = first + (height - first) / 2;

			for (int level = first; level < height; level++) {
				int radius = level < middle ? 2 : 1;
				BlockPos base = spine.get(level);

				for (int dx = -radius; dx <= radius; dx++) {
					for (int dz = -radius; dz <= radius; dz++) {
						if (dx == 0 && dz == 0 || Math.abs(dx) + Math.abs(dz) > radius + 1
							|| random.nextFloat() > tree.branchChance()) {
							continue;
						}

						foliage.putIfAbsent(base.offset(dx, 0, dz).immutable(), tree.leaves());
					}
				}
			}

			foliage.putIfAbsent(spine.get(height - 1).above().immutable(), tree.leaves());
		}
	},
	/** Baobab: a thick barrel of a trunk that ends in a handful of stubby upward arms. */
	BAOBAB {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			int shoulder = Math.max(2, height - 2);

			for (int level = 0; level < shoulder; level++) {
				for (int dx = 0; dx < 2; dx++) {
					for (int dz = 0; dz < 2; dz++) {
						logs.putIfAbsent(origin.offset(dx, level, dz).immutable(), tree.trunk());
					}
				}
			}

			BlockPos top = origin.offset(0, shoulder, 0);
			logs.putIfAbsent(top.immutable(), tree.trunk());
			logs.putIfAbsent(top.above().immutable(), tree.trunk());

			for (Direction direction : shuffled(random)) {
				if (random.nextFloat() > 0.4F + tree.branchChance() * 0.6F) {
					continue;
				}

				BlockPos tip = limb(logs, tree.trunk(), top, direction, 2 + random.nextInt(2), 2);
				ellipsoid(foliage, tree.leaves(), tip, 1 + random.nextInt(2), 1, 1.2F, random);
			}
		}
	},
	/** Palm: a leaning shaft with nothing on it but a star of fronds at the very top. */
	PALM {
		@Override
		public void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
			Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage) {
			List<BlockPos> spine = new ArrayList<>(height);
			BlockPos cursor = origin;
			Direction lean = Direction.Plane.HORIZONTAL.getRandomDirection(random);
			int leanEvery = 2 + random.nextInt(2);

			for (int level = 0; level < height; level++) {
				spine.add(cursor.immutable());

				if (level > 1 && level % leanEvery == 0) {
					cursor = cursor.relative(lean);
				}

				cursor = cursor.above();
			}

			trunk(logs, tree.trunk(), spine);

			BlockPos crown = spine.get(height - 1);
			foliage.putIfAbsent(crown.above().immutable(), tree.leaves());

			for (int[] ray : RAYS) {
				if (random.nextFloat() > 0.5F + tree.branchChance() * 0.5F) {
					continue;
				}

				int length = tree.canopyRadius() + 1 + random.nextInt(2);

				for (int step = 1; step <= length; step++) {
					int droop = step <= length - 2 ? 0 : step - (length - 2);
					BlockPos pos = crown.offset(ray[0] * step, -droop, ray[1] * step);
					logs.putIfAbsent(pos.immutable(), rayState(tree.trunk(), ray[0]));
					foliage.putIfAbsent(pos.immutable(), tree.leaves());
					foliage.putIfAbsent(pos.below().immutable(), tree.leaves());
				}
			}
		}
	};

	/** The eight horizontal rays a frond can be laid along. */
	private static final int[][] RAYS = { {1, 0}, {1, 1}, {0, 1}, { -1, 1}, { -1, 0}, { -1, -1}, {0, -1}, {1, -1} };

	public abstract void grow(FancyTreeConfiguration tree, RandomSource random, BlockPos origin, int height,
		Map<BlockPos, BlockState> logs, Map<BlockPos, BlockState> foliage);

	/**
	 * Whether this form spreads a crown sideways above the trunk. The palm, the columnar shapes and
	 * the baobab grow straight up instead, so they need less headroom and can be planted nearer a
	 * cliff top or the build limit.
	 */
	public boolean spreadsCrown() {
		return this != PALM && this != COLUMNAR && this != BAOBAB;
	}

	public static TreeForm byName(String name) {
		for (TreeForm form : values()) {
			if (form.name().toLowerCase(Locale.ROOT).equals(name)) {
				return form;
			}
		}

		throw new IllegalArgumentException("unknown tree form " + name);
	}

	/** The trunk line, optionally bent sideways partway up so the tree does not read as a pole. */
	static List<BlockPos> spine(RandomSource random, BlockPos origin, int height, float leanChance) {
		List<BlockPos> spine = new ArrayList<>(height);
		BlockPos cursor = origin;

		for (int i = 0; i < height; i++) {
			spine.add(cursor.immutable());
			cursor = cursor.above();
		}

		if (height >= 5 && random.nextFloat() < leanChance) {
			int bend = height / 4 + random.nextInt(height / 2);
			Direction lean = Direction.Plane.HORIZONTAL.getRandomDirection(random);

			for (int i = bend; i < height; i++) {
				spine.set(i, spine.get(i).relative(lean));
			}
		}

		return spine;
	}

	static void trunk(Map<BlockPos, BlockState> logs, BlockState bark, List<BlockPos> spine) {
		BlockPos previous = null;

		for (BlockPos pos : spine) {
			BlockState state = bark;

			if (previous != null) {
				int dx = pos.getX() - previous.getX();
				int dz = pos.getZ() - previous.getZ();

				if ((dx != 0 || dz != 0) && state.hasProperty(BlockStateProperties.AXIS)) {
					state = state.setValue(BlockStateProperties.AXIS, dx != 0 ? Direction.Axis.X : Direction.Axis.Z);
				}
			}

			logs.put(pos.immutable(), state);
			previous = pos;
		}
	}

	/** A limb laid out sideways, gaining or losing `rise` blocks over its length. Returns the tip. */
	static BlockPos limb(Map<BlockPos, BlockState> logs, BlockState bark, BlockPos base, Direction direction, int length, int rise) {
		BlockState limb = bark.hasProperty(BlockStateProperties.AXIS)
			? bark.setValue(BlockStateProperties.AXIS, direction.getAxis())
			: bark;
		BlockPos tip = base;

		for (int step = 1; step <= length; step++) {
			tip = offset(base, direction, step, length, rise);
			logs.putIfAbsent(tip.immutable(), limb);
		}

		return tip;
	}

	static BlockPos offset(BlockPos base, Direction direction, int step, int length, int rise) {
		int y = (int) Math.round(rise * step / (double) length);
		return base.offset(direction.getStepX() * step, y, direction.getStepZ() * step);
	}

	static void blob(Map<BlockPos, BlockState> foliage, BlockState leaf, BlockPos center, int radius) {
		for (int dx = -radius; dx <= radius; dx++) {
			for (int dy = -radius; dy <= radius; dy++) {
				for (int dz = -radius; dz <= radius; dz++) {
					if (dx * dx + dy * dy + dz * dz <= radius * radius) {
						foliage.putIfAbsent(center.offset(dx, dy, dz).immutable(), leaf);
					}
				}
			}
		}
	}

	static void ellipsoid(Map<BlockPos, BlockState> foliage, BlockState leaf, BlockPos center, int radius, int vertical,
		float fullness, RandomSource random) {
		for (int dx = -radius; dx <= radius; dx++) {
			for (int dz = -radius; dz <= radius; dz++) {
				for (int dy = -vertical; dy <= vertical; dy++) {
					double spread = (dx * dx + dz * dz) / (double) (radius * radius) + (dy * dy) / (double) (vertical * vertical);

					if (spread <= fullness + random.nextFloat() * 0.35) {
						foliage.putIfAbsent(center.offset(dx, dy, dz).immutable(), leaf);
					}
				}
			}
		}
	}

	/** A flat wide crown two blocks thick, which is what an acacia reads as from below. */
	static void disc(Map<BlockPos, BlockState> foliage, BlockState leaf, BlockPos center, int radius, float fullness,
		RandomSource random) {
		for (int dx = -radius; dx <= radius; dx++) {
			for (int dz = -radius; dz <= radius; dz++) {
				double offset = Math.sqrt(dx * dx + dz * dz);

				if (offset > radius + 0.5 || (offset < radius - 1.0 && random.nextFloat() > fullness)) {
					continue;
				}

				for (int dy = 0; dy <= 1; dy++) {
					foliage.putIfAbsent(center.offset(dx, dy, dz).immutable(), leaf);
				}
			}
		}
	}

	/** A strand of leaves hanging down from a limb tip, which is what makes a willow a willow. */
	static void curtain(Map<BlockPos, BlockState> foliage, BlockState leaf, BlockPos top, int drop, RandomSource random) {
		BlockPos cursor = top;

		for (int i = 0; i < drop; i++) {
			foliage.putIfAbsent(cursor.immutable(), leaf);
			cursor = cursor.below();

			if (i > 1 && random.nextFloat() < 0.25F) {
				cursor = cursor.relative(Direction.Plane.HORIZONTAL.getRandomDirection(random));
			}
		}
	}

	private static BlockState rayState(BlockState bark, int dx) {
		return bark.hasProperty(BlockStateProperties.AXIS)
			? bark.setValue(BlockStateProperties.AXIS, dx == 0 ? Direction.Axis.Z : Direction.Axis.X)
			: bark;
	}

	private static Direction[] shuffled(RandomSource random) {
		Direction[] ring = { Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST };

		for (int i = ring.length - 1; i > 0; i--) {
			int j = random.nextInt(i + 1);
			Direction swap = ring[i];
			ring[i] = ring[j];
			ring[j] = swap;
		}

		return ring;
	}
}
