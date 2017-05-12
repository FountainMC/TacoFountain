package org.fountainmc.taco

import com.google.common.collect.ImmutableList
import net.minecraft.server.DedicatedServer
import net.minecraft.server.PlayerList
import org.fountainmc.api.Fountain
import org.fountainmc.api.Material
import org.fountainmc.api.Server
import org.fountainmc.api.command.CommandManager
import org.fountainmc.api.enchantments.EnchantmentType
import org.fountainmc.api.entity.EntityType
import org.fountainmc.api.entity.Player
import org.fountainmc.api.entity.data.EntityDataFactory
import org.fountainmc.api.entity.data.PlayerData
import org.fountainmc.api.event.EventManager
import org.fountainmc.api.inventory.item.ItemFactory
import org.fountainmc.api.plugin.PluginManager
import org.fountainmc.api.scheduler.Scheduler
import org.slf4j.ILoggerFactory
import org.slf4j.Logger
import java.net.InetSocketAddress

class TacoFountainServer(
        val handle: DedicatedServer,
        val playerList: PlayerList
) : Server {
    init {
        Fountain.setImplementation(this) // There can be only one!
    }
    override val name: String
        get() = "TacoFountain"
    override val version: String
        get() = handle.version
    override val motd: String
        get() = handle.motd
    override val maxPlayers: Int
        get() = playerList.maxPlayers
    override val launchArguments: ImmutableList<String>
        get() = launchArguments
    override val address: InetSocketAddress
        get() = InetSocketAddress.createUnresolved(handle.serverIp, handle.port)

    //
    // === TODO ====
    //

    override fun getMaterial(name: String): Material<*> {
        TODO("Not yet implemented!")
    }

    override fun getMaterial(id: Int): Material<*> {
        TODO("Not yet implemented!")
    }

    override fun getEntityType(name: String): EntityType<*> {
        TODO("Not yet implemented!")
    }

    override fun calculateTotalExperience(experienceData: PlayerData.ExperienceData): Long {
        TODO("Not yet implemented!")
    }

    override fun calculateExperienceData(totalExperience: Long): PlayerData.ExperienceData {
        TODO("Not yet implemented!")
    }

    override fun getEnchantmentTypeByName(name: String): EnchantmentType {
        TODO("Not yet implemented!")
    }

    override val onlinePlayerCount: Int
        get() = TODO("Not yet implemented!")
    override val onlinePlayers: List<Player>
        get() = TODO("Not yet implemented!")
    override val blockingScheduler: Scheduler
        get() = TODO("Not yet implemented!")
    override val asynchronousScheduler: Scheduler
        get() = TODO("Not yet implemented!")
    override val entityDataFactory: EntityDataFactory
        get() = TODO("Not yet implemented!")
    override val loggerFactory: ILoggerFactory
        get() = TODO("Not yet implemented!")
    override val serverLogger: Logger
        get() = TODO("Not yet implemented!")
    override val itemFactory: ItemFactory
        get() = TODO("Not yet implemented!")
    override val pluginManager: PluginManager
        get() = TODO("Not yet implemented!")
    override val commandManager: CommandManager
        get() = TODO("Not yet implemented!")
    override val eventManager: EventManager
        get() = TODO("Not yet implemented!")
    override val owner: String
        get() = TODO("Not yet implemented!")
}