package org.fountainmc.taco

import net.minecraft.server.WorldServer
import org.bukkit.craftbukkit.CraftWorld
import org.fountainmc.api.world.Chunk
import org.fountainmc.api.world.World
import org.fountainmc.api.world.block.BlockState
import org.fountainmc.api.world.tileentity.TileEntity

class TacoFountianWorld(
        override val server: TacoFountainServer,
        val handle: WorldServer,
        val bukkit: CraftWorld
): World {
    override val name: String
        get() = bukkit.name

    override fun getChunk(x: Int, y: Int): Chunk {
        TODO("Not yet implemented!")
    }

    override fun getBlock(x: Int, y: Int, z: Int): BlockState {
        TODO("Not yet implemented!")
    }

    override fun getTileEntity(x: Int, y: Int, z: Int): TileEntity<*> {
        TODO("Not yet implemented!")
    }

    override fun setBlock(x: Int, y: Int, z: Int, state: BlockState) {
        TODO("Not yet implemented!")
    }
}