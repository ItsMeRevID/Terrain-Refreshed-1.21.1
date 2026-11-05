package net.revskymc.terrainrefreshed.mixin;

import net.minecraft.core.Holder;
import net.minecraft.core.HolderGetter;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.biome.MultiNoiseBiomeSourceParameterList;
import net.revskymc.terrainrefreshed.worldgen.OverworldBiomeExtender;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/**
 * Replaces the climate list of the vanilla overworld preset with one that also contains the
 * Terrain Refreshed biomes.
 */
@Mixin(MultiNoiseBiomeSourceParameterList.class)
public abstract class MultiNoiseBiomeSourceParameterListMixin {
	private static final ResourceLocation OVERWORLD_PRESET = ResourceLocation.withDefaultNamespace("overworld");

	@Shadow
	private Climate.ParameterList<Holder<Biome>> parameters;

	@Unique
	private Climate.ParameterList<Holder<Biome>> terrainrefreshed$extended;

	@Inject(method = "<init>", at = @At("RETURN"))
	private void terrainrefreshed$extend(
		final MultiNoiseBiomeSourceParameterList.Preset preset,
		final HolderGetter<Biome> biomes,
		final CallbackInfo ci
	) {
		if (!OVERWORLD_PRESET.equals(preset.id())) {
			return;
		}

		this.terrainrefreshed$extended = OverworldBiomeExtender.extend(this.parameters, biomes);
	}

	@Inject(method = "parameters", at = @At("HEAD"), cancellable = true)
	private void terrainrefreshed$parameters(final CallbackInfoReturnable<Climate.ParameterList<Holder<Biome>>> cir) {
		if (this.terrainrefreshed$extended != null) {
			cir.setReturnValue(this.terrainrefreshed$extended);
		}
	}
}
