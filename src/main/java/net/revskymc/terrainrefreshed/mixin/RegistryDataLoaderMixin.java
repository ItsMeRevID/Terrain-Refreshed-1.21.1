package net.revskymc.terrainrefreshed.mixin;

import com.google.gson.JsonElement;
import net.minecraft.resources.RegistryDataLoader;
import net.revskymc.terrainrefreshed.compat.BiomeJsonAdapter;
import net.revskymc.terrainrefreshed.compat.BiomeSchema;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyArg;

/**
 * Rewrites the biome definitions of the mod into the schema the running game expects. The hook
 * sits on the decode call of the registry loader, so the game keeps its own loading logic.
 */
@Mixin(RegistryDataLoader.class)
public abstract class RegistryDataLoaderMixin {
	@ModifyArg(
		method = "loadElementFromResource",
		at = @At(
			value = "INVOKE",
			target = "Lcom/mojang/serialization/Decoder;parse(Lcom/mojang/serialization/DynamicOps;Ljava/lang/Object;)Lcom/mojang/serialization/DataResult;"
		),
		index = 1
	)
	private static Object terrainrefreshed$adaptBiomeSchema(final Object json) {
		if (json instanceof JsonElement element) {
			return BiomeJsonAdapter.adapt(element, BiomeSchema.current());
		}

		return json;
	}
}
